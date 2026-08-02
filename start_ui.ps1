# 达芬七 · Z-Image launcher (Unicode-safe)
# Called by 启动.bat — do not rely on cmd.exe for Chinese text.
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$PackRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $PackRoot) { $PackRoot = $PSScriptRoot }
$PackRoot = (Resolve-Path $PackRoot).Path
Set-Location $PackRoot

$LogDir = Join-Path $PackRoot "userdata\logs"
try {
  New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
  $LauncherLog = Join-Path $LogDir ("launcher-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
  Start-Transcript -Path $LauncherLog -Force | Out-Null
} catch {}

function Say([string]$msg) { Write-Host $msg }
function SayBlank { Write-Host "" }

$LauncherMutex = New-Object System.Threading.Mutex($false, "Local\DavinciSevenZImageLauncher")
$OwnsLauncherMutex = $false
try {
  $OwnsLauncherMutex = $LauncherMutex.WaitOne(0, $false)
} catch [System.Threading.AbandonedMutexException] {
  $OwnsLauncherMutex = $true
}

if (-not $OwnsLauncherMutex) {
  Say "[提示 INFO] 本程序已经在启动或运行，请不要重复双击。"
  Say "Another Davinci Z-Image launcher is already starting or running."
  Say "正在等待界面 / waiting for UI: http://127.0.0.1:8888"
  for ($i = 1; $i -le 120; $i++) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8888" -TimeoutSec 2
      if ($response.StatusCode -ge 200) {
        try { Start-Process "http://127.0.0.1:8888" } catch {}
        exit 0
      }
    } catch {}
    Start-Sleep -Seconds 2
  }
  Say "[错误 ERROR] 等待现有程序超时。请关闭旧窗口后再试。"
  Read-Host "按回车退出 / Press Enter to exit"
  exit 1
}

$Host.UI.RawUI.WindowTitle = "达芬七 Z-Image"

SayBlank
Say "================================================================"
Say "  达芬七 · Z-Image  /  Davinci Seven  Z-Image"
Say "  https://x.com/davinci_seven"
Say "================================================================"
SayBlank

$enginePack = Join-Path $PackRoot "engine\ComfyUI\main.py"
$engineSib = Join-Path (Split-Path $PackRoot -Parent) "ComfyUI-zimage\ComfyUI\main.py"

if (Test-Path $enginePack) {
  $EngineRoot = (Resolve-Path (Join-Path $PackRoot "engine")).Path
} elseif (Test-Path $engineSib) {
  $EngineRoot = (Resolve-Path (Join-Path (Split-Path $PackRoot -Parent) "ComfyUI-zimage")).Path
} else {
  Say "[错误 ERROR] 找不到引擎 / Engine not found"
  Say "  请把引擎放在: $PackRoot\engine\"
  Say "  Put engine at: this-folder\engine\"
  Say "  或并排放: ComfyUI-zimage"
  Say "  Or sibling folder: ComfyUI-zimage"
  SayBlank
  Read-Host "按回车退出 / Press Enter to exit"
  exit 1
}

$PythonExe = Join-Path $EngineRoot "python\python.exe"
if (-not (Test-Path $PythonExe)) {
  Say "[错误 ERROR] 找不到 Python / Python not found"
  Say "  $PythonExe"
  SayBlank
  Read-Host "按回车退出 / Press Enter to exit"
  exit 1
}

$UiMain = Join-Path $PackRoot "app\main.py"
if (-not (Test-Path $UiMain)) {
  Say "[错误 ERROR] 找不到界面 / UI entry not found"
  Say "  $UiMain"
  SayBlank
  Read-Host "按回车退出 / Press Enter to exit"
  exit 1
}

$env:PYTHONPATH = Join-Path $EngineRoot "python\Lib\site-packages"
$GradioPort = 8888
$ComfyPort = 7777
if ($env:DAVINCI_UI_PORT -match "^\d+$") {
  $GradioPort = [int]$env:DAVINCI_UI_PORT
}
if ($env:DAVINCI_COMFY_PORT -match "^\d+$") {
  $ComfyPort = [int]$env:DAVINCI_COMFY_PORT
}
$Reused = $false

Say "[引擎 engine] $EngineRoot"
Say "[Python]      $PythonExe"
Say "[端口 ports]  UI=$GradioPort  Comfy=$ComfyPort"
SayBlank

function Get-ListenPid([int]$port) {
  if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
    $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($connection) {
      return [int]$connection.OwningProcess
    }
    return $null
  } else {
    # Fallback for older Windows. Match the numeric endpoint and final PID only;
    # do not depend on localized words such as LISTENING.
    $lines = netstat -ano -p tcp 2>$null | Select-String "127\.0\.0\.1:$port\s"
    foreach ($line in $lines) {
      if ($line.Line -match "\s(\d+)\s*$") {
        return [int]$Matches[1]
      }
    }
  }
  return $null
}

function Show-Port([int]$port, $procId) {
  if (-not $procId) { return }
  $name = "unknown"
  try {
    $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($p) { $name = $p.ProcessName }
  } catch {}
  Say "    端口 port $port  ->  PID $procId  ($name)"
}

Say "[0/3] 检查端口 / checking ports..."
$uiPid = Get-ListenPid $GradioPort
$comfyPid = Get-ListenPid $ComfyPort

if ($uiPid -or $comfyPid) {
  SayBlank
  Say "  ------------------------------------------------"
  Say "  端口已被占用 / Ports already in use:"
  Say "  ------------------------------------------------"
  if ($uiPid) { Show-Port $GradioPort $uiPid }
  if ($comfyPid) { Show-Port $ComfyPort $comfyPid }
  SayBlank
  Say "  请选择 / Choose one:"
  SayBlank
  Say "  [K] 结束占用进程并重新启动"
  Say "      Kill those processes and start fresh"
  SayBlank
  Say "  [R] 复用已在运行的引擎（仅当界面端口空闲）"
  Say "      Reuse running engine (only if UI port is free)"
  SayBlank
  Say "  [Q] 退出，自己去关掉"
  Say "      Quit and close them yourself"
  SayBlank

  $choice = Read-Host "请输入 K / R / Q  —  Type K / R / Q"
  $choice = ($choice | ForEach-Object { $_.Trim().ToUpperInvariant() })

  if ($choice -eq "Q") {
    Say "已取消 / Cancelled. Nothing was closed."
    SayBlank
    Read-Host "按回车退出 / Press Enter to exit"
    exit 0
  }

  if ($choice -eq "R") {
    if ($uiPid) {
      Say "[错误 ERROR] 界面端口 $GradioPort 仍被占用，无法复用。"
      Say "UI port busy — cannot reuse. Close it or choose K."
      SayBlank
      Read-Host "按回车退出 / Press Enter to exit"
      exit 1
    }
    if ($comfyPid) {
      Say "[1/3] 复用引擎 / reusing engine on $ComfyPort"
      $Reused = $true
    }
  } else {
    # default K
    Say "[0/3] 正在结束占用进程 / closing them..."
    if ($uiPid) {
      try { Stop-Process -Id $uiPid -Force -ErrorAction SilentlyContinue } catch {}
    }
    if ($comfyPid) {
      try { Stop-Process -Id $comfyPid -Force -ErrorAction SilentlyContinue } catch {}
    }
    Start-Sleep -Seconds 2
    $uiStillBusy = Get-ListenPid $GradioPort
    $comfyStillBusy = Get-ListenPid $ComfyPort
    if ($uiStillBusy -or $comfyStillBusy) {
      SayBlank
      Say "[错误 ERROR] 无法结束占用端口的进程，可能属于另一个Windows用户。"
      Say "Could not stop the port owner. It may belong to another Windows user."
      if ($uiStillBusy) { Show-Port $GradioPort $uiStillBusy }
      if ($comfyStillBusy) { Show-Port $ComfyPort $comfyStillBusy }
      Say "请以管理员身份打开任务管理器结束该PID，或者重启电脑后再启动本包。"
      Say "Use Task Manager as administrator to end that PID, or restart Windows."
      Read-Host "按回车退出 / Press Enter to exit"
      exit 1
    }
    $Reused = $false
  }
}

if (-not $Reused) {
  Say "[1/3] 启动引擎 / starting Comfy on $ComfyPort ..."
  $comfyArgs = @(
    "-s", "ComfyUI\main.py",
    "--windows-standalone-build",
    "--listen", "127.0.0.1",
    "--port", "$ComfyPort",
    "--disable-auto-launch"
  )
  $comfyOutLog = Join-Path $LogDir "comfy-latest.out.log"
  $comfyErrLog = Join-Path $LogDir "comfy-latest.err.log"
  $ComfyProcess = Start-Process -FilePath $PythonExe -ArgumentList $comfyArgs -WorkingDirectory $EngineRoot -WindowStyle Hidden `
    -RedirectStandardOutput $comfyOutLog -RedirectStandardError $comfyErrLog -PassThru
}

Say "[2/3] 等待引擎就绪 / waiting for Comfy on $ComfyPort ..."
$waitScript = Join-Path $PackRoot "app\wait_comfy.py"
& $PythonExe $waitScript $ComfyPort
if ($LASTEXITCODE -ne 0) {
  Say "[错误 ERROR] 引擎未能启动，暂不打开空白界面。"
  Say "ComfyUI did not become ready. The UI will not open."
  if ($ComfyProcess -and $ComfyProcess.HasExited) {
    Say "引擎进程已退出 / Engine process exited: $($ComfyProcess.ExitCode)"
  }
  SayBlank
  Say "最近错误 / latest errors:"
  if (Test-Path $comfyErrLog) {
    Get-Content -LiteralPath $comfyErrLog -Tail 20 | ForEach-Object { Say "  $_" }
  }
  SayBlank
  Say "请双击“导出诊断信息.bat”，把生成的txt发给AI或作者。"
  Say "Run 导出诊断信息.bat and share the generated txt."
  Read-Host "按回车退出 / Press Enter to exit"
  exit 1
} else {
  Say "[完成 ok] 引擎已就绪 / Comfy is ready"
}

if ($env:DAVINCI_STARTUP_TEST -eq "1") {
  Say "[QA] 启动测试通过，正在清理测试进程 / startup test passed; cleaning up"
  $testPid = Get-ListenPid $ComfyPort
  if ($testPid) {
    try { Stop-Process -Id $testPid -Force -ErrorAction SilentlyContinue } catch {}
  }
  exit 0
}

Say "[3/3] 启动界面 / starting UI  http://127.0.0.1:$GradioPort"
Start-Sleep -Seconds 1
if ($env:DAVINCI_NO_BROWSER -ne "1") {
  try { Start-Process "http://127.0.0.1:$GradioPort" } catch {}
}

$uiArgs = @($UiMain, "--server_port", "$GradioPort", "--server_name", "127.0.0.1")
& $PythonExe @uiArgs
$ec = $LASTEXITCODE

SayBlank
Say "界面已关闭 / UI closed."

if (-not $Reused) {
  Say "正在清理引擎 / cleaning Comfy on $ComfyPort ..."
  $left = Get-ListenPid $ComfyPort
  if ($left) {
    try { Stop-Process -Id $left -Force -ErrorAction SilentlyContinue } catch {}
  }
}

Say "完成 / done.  exit code $ec"
SayBlank
if ($OwnsLauncherMutex) {
  try { $LauncherMutex.ReleaseMutex() } catch {}
}
$LauncherMutex.Dispose()
Read-Host "按回车退出 / Press Enter to exit"
exit $ec
