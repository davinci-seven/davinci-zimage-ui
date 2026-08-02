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

# 说明：关浏览器 ≠ 关后台。引擎 Comfy 用隐藏 python 跑在 7777，
# 只关网页 / 点窗口 X 时，若脚本没跑完清理，7777 会一直占着。
function Stop-PortOwners {
  param([int]$Ui, [int]$Comfy)
  if ($Ui) {
    try { Stop-Process -Id $Ui -Force -ErrorAction SilentlyContinue } catch {}
  }
  if ($Comfy) {
    try { Stop-Process -Id $Comfy -Force -ErrorAction SilentlyContinue } catch {}
  }
  Start-Sleep -Seconds 2
}

if ($uiPid -or $comfyPid) {
  SayBlank
  # 最常见：只剩引擎（界面已关）→ 自动复用，不再打断用户
  if ((-not $uiPid) -and $comfyPid) {
    Say "  [提示] 检测到引擎还在后台（端口 $ComfyPort / PID $comfyPid）。"
    Say "  关浏览器或关窗口不会关掉引擎——这是正常现象，不是假关失败。"
    Say "  将自动复用该引擎，直接开新界面（更快）。"
    Say "  若要彻底重开引擎，请下次启动时选 K，或先结束 PID $comfyPid。"
    SayBlank
    Say "[1/3] 复用引擎 / reusing engine on $ComfyPort"
    $Reused = $true
  }
  # 界面还占着，引擎可能也在 → 问用户
  elseif ($uiPid) {
    Say "  ------------------------------------------------"
    Say "  端口已被占用（上次可能没关干净）"
    Say "  ------------------------------------------------"
    if ($uiPid) { Show-Port $GradioPort $uiPid }
    if ($comfyPid) { Show-Port $ComfyPort $comfyPid }
    SayBlank
    Say "  说明：关浏览器 ≠ 关后台。引擎是隐藏的 python 进程。"
    SayBlank
    Say "  [K] 全部杀掉并重新启动（推荐，改代码后必选）"
    Say "  [R] 只复用引擎（界面端口必须空闲；当前界面仍占用时不可用）"
    Say "  [Q] 退出"
    SayBlank

    $choice = Read-Host "请输入 K / R / Q（直接回车 = K）"
    $choice = ($choice | ForEach-Object { $_.Trim().ToUpperInvariant() })
    if (-not $choice) { $choice = "K" }

    if ($choice -eq "Q") {
      Say "已取消。"
      Read-Host "按回车退出 / Press Enter to exit"
      exit 0
    }

    if ($choice -eq "R") {
      if ($uiPid) {
        Say "[错误] 界面端口 $GradioPort 仍被占用，无法只复用引擎。请选 K。"
        Read-Host "按回车退出 / Press Enter to exit"
        exit 1
      }
      Say "[1/3] 复用引擎 / reusing engine on $ComfyPort"
      $Reused = $true
    } else {
      Say "[0/3] 正在结束占用进程..."
      Stop-PortOwners -Ui $uiPid -Comfy $comfyPid
      $uiStillBusy = Get-ListenPid $GradioPort
      $comfyStillBusy = Get-ListenPid $ComfyPort
      if ($uiStillBusy -or $comfyStillBusy) {
        Say "[错误] 无法结束占用进程。请打开任务管理器结束 python，或重启电脑。"
        if ($uiStillBusy) { Show-Port $GradioPort $uiStillBusy }
        if ($comfyStillBusy) { Show-Port $ComfyPort $comfyStillBusy }
        Read-Host "按回车退出 / Press Enter to exit"
        exit 1
      }
      $Reused = $false
    }
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
$ec = 0
try {
  & $PythonExe @uiArgs
  $ec = $LASTEXITCODE
} finally {
  SayBlank
  Say "界面已关闭 / UI closed."
  # 本会话自己拉起的引擎：尽量收掉。若启动时选了复用(R/自动复用)，默认保留引擎，
  # 方便下次秒开；若要连引擎一起关，设环境变量 DAVINCI_KILL_ENGINE_ON_EXIT=1
  $killEngine = ($env:DAVINCI_KILL_ENGINE_ON_EXIT -eq "1") -or (-not $Reused)
  if ($killEngine) {
    Say "正在清理引擎 / cleaning Comfy on $ComfyPort ..."
    $left = Get-ListenPid $ComfyPort
    if ($left) {
      try { Stop-Process -Id $left -Force -ErrorAction SilentlyContinue } catch {}
    }
    Start-Sleep -Seconds 1
    $still = Get-ListenPid $ComfyPort
    if ($still) {
      Say "  [提示] 引擎可能仍在 PID $still（关黑窗口 X 时有时杀不干净）。"
      Say "  下次启动会自动处理，或任务管理器结束 python。"
    } else {
      Say "  引擎已结束。"
    }
  } else {
    Say "  已保留后台引擎（复用模式）。关浏览器不会关引擎，下次启动会直接复用。"
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
