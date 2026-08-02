# 达芬七 · Z-Image 一键诊断
# 只读取系统和包内信息，不修改模型、配置或用户图片。
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$PackRoot = (Resolve-Path $PSScriptRoot).Path
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OutputFile = Join-Path $PackRoot "诊断信息-$Stamp.txt"
$Lines = New-Object System.Collections.Generic.List[string]
$UserName = [Environment]::UserName
$ComputerName = [Environment]::MachineName
$UserProfile = [Environment]::GetFolderPath("UserProfile")

function Redact([object]$Value) {
  if ($null -eq $Value) { return "" }
  $text = [string]$Value
  if ($UserProfile) {
    $text = $text.Replace($UserProfile, "%USERPROFILE%")
  }
  if ($UserName) {
    $text = $text.Replace($UserName, "<USER>")
  }
  if ($ComputerName) {
    $text = $text.Replace($ComputerName, "<PC>")
  }
  return $text
}

function Add-Line([object]$Value = "") {
  $Lines.Add((Redact $Value))
}

function Add-Section([string]$Title) {
  Add-Line ""
  Add-Line "================================================================"
  Add-Line $Title
  Add-Line "================================================================"
}

function Add-CommandOutput([object[]]$Output) {
  foreach ($item in $Output) {
    Add-Line $item
  }
}

Add-Line "达芬七 · Z-Image 诊断信息"
Add-Line "生成时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')"
Add-Line "版本: v1.4.0"
Add-Line ""
Add-Line "可以把本文件拖给AI分析。用户名、电脑名和用户目录已自动遮挡。"
Add-Line "分享前仍建议快速浏览一次；本报告不收集提示词、生成图片或网络密码。"

Add-Section "1. Windows"
try {
  $os = Get-CimInstance Win32_OperatingSystem
  Add-Line "系统: $($os.Caption)"
  Add-Line "版本: $($os.Version)  Build $($os.BuildNumber)"
  Add-Line "架构: $($os.OSArchitecture)"
  Add-Line "最近启动: $($os.LastBootUpTime)"
  Add-Line "可用内存: $([math]::Round($os.FreePhysicalMemory / 1MB, 2)) GB"
} catch {
  Add-Line "读取Windows信息失败: $($_.Exception.Message)"
}
try {
  $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
  Add-Line "CPU: $($cpu.Name)"
  Add-Line "核心/线程: $($cpu.NumberOfCores) / $($cpu.NumberOfLogicalProcessors)"
} catch {
  Add-Line "读取CPU信息失败: $($_.Exception.Message)"
}
try {
  Add-Line "PowerShell: $($PSVersionTable.PSVersion)"
  Add-Line "执行策略: $(Get-ExecutionPolicy)"
} catch {}

Add-Section "2. 显卡与驱动"
try {
  $gpus = Get-CimInstance Win32_VideoController
  foreach ($gpu in $gpus) {
    Add-Line "显卡: $($gpu.Name)"
    Add-Line "驱动: $($gpu.DriverVersion)"
    if ($gpu.AdapterRAM) {
      Add-Line "Windows报告显存（可能不准，以nvidia-smi为准）: $([math]::Round([double]$gpu.AdapterRAM / 1GB, 2)) GB"
    }
    Add-Line "---"
  }
} catch {
  Add-Line "读取显卡信息失败: $($_.Exception.Message)"
}

$NvidiaSmi = $null
try {
  $cmd = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
  if ($cmd) { $NvidiaSmi = $cmd.Source }
} catch {}
if (-not $NvidiaSmi) {
  $candidate = Join-Path $env:WINDIR "System32\nvidia-smi.exe"
  if (Test-Path $candidate) { $NvidiaSmi = $candidate }
}
if ($NvidiaSmi) {
  Add-Line "nvidia-smi: 已找到"
  try {
    $smi = & $NvidiaSmi --query-gpu=name,driver_version,memory.total,memory.used,temperature.gpu,compute_cap --format=csv,noheader 2>&1
    Add-CommandOutput $smi
  } catch {
    Add-Line "nvidia-smi运行失败: $($_.Exception.Message)"
  }
} else {
  Add-Line "nvidia-smi: 未找到（可能没有NVIDIA显卡或驱动未安装）"
}

Add-Section "3. 包路径与磁盘"
Add-Line "包路径: $PackRoot"
Add-Line "路径长度: $($PackRoot.Length)"
try {
  $rootPath = [IO.Path]::GetPathRoot($PackRoot)
  $driveName = $rootPath.TrimEnd("\").TrimEnd(":")
  $drive = Get-PSDrive -Name $driveName
  Add-Line "所在磁盘: $rootPath"
  Add-Line "剩余空间: $([math]::Round($drive.Free / 1GB, 2)) GB"
  Add-Line "已用空间: $([math]::Round($drive.Used / 1GB, 2)) GB"
} catch {
  Add-Line "读取磁盘空间失败: $($_.Exception.Message)"
}

Add-Section "4. 关键文件"
$CriticalFiles = @(
  "启动.bat",
  "start_ui.ps1",
  "app\main.py",
  "app\wait_comfy.py",
  "app\workflows\txt2img.json",
  "app\workflows\txt2img_gguf.json",
  "assets\styles\styles.json",
  "engine\python\python.exe",
  "engine\ComfyUI\main.py"
)
foreach ($relative in $CriticalFiles) {
  $full = Join-Path $PackRoot $relative
  if (Test-Path $full) {
    $item = Get-Item $full
    Add-Line "[OK] $relative  ($($item.Length) bytes)"
  } else {
    Add-Line "[缺失 MISSING] $relative"
  }
}

Add-Section "5. 内置Python与CUDA"
$PythonExe = Join-Path $PackRoot "engine\python\python.exe"
if (Test-Path $PythonExe) {
  try {
    Add-CommandOutput (& $PythonExe --version 2>&1)
    $pyCode = @"
import sys
print("executable=" + sys.executable)
try:
    import torch
    print("torch=" + str(torch.__version__))
    print("torch_cuda=" + str(torch.version.cuda))
    print("cuda_available=" + str(torch.cuda.is_available()))
    print("gpu_count=" + str(torch.cuda.device_count()))
    if torch.cuda.is_available():
        for i in range(torch.cuda.device_count()):
            p = torch.cuda.get_device_properties(i)
            print("gpu_%d=%s | %.2f GB" % (i, p.name, p.total_memory / 1024**3))
except Exception as e:
    print("torch_check_error=" + repr(e))
for name in ("gradio", "yaml", "PIL", "aiohttp"):
    try:
        mod = __import__(name)
        print("import_%s=OK %s" % (name, getattr(mod, "__version__", "")))
    except Exception as e:
        print("import_%s=ERROR %r" % (name, e))
"@
    $tempPy = Join-Path ([IO.Path]::GetTempPath()) ("davinciz-diagnostic-" + $PID + ".py")
    try {
      $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
      [System.IO.File]::WriteAllText($tempPy, $pyCode, $utf8NoBom)
      Add-CommandOutput (& $PythonExe $tempPy 2>&1)
    } finally {
      Remove-Item -LiteralPath $tempPy -Force -ErrorAction SilentlyContinue
    }
  } catch {
    Add-Line "内置Python检查失败: $($_.Exception.Message)"
  }
} else {
  Add-Line "无法检查：engine\python\python.exe不存在"
}

Add-Section "6. 配置文件"
$JsonFiles = @(
  "app\workflows\txt2img.json",
  "app\workflows\txt2img_gguf.json",
  "assets\styles\styles.json",
  "assets\prompts\presets.json"
)
foreach ($relative in $JsonFiles) {
  $full = Join-Path $PackRoot $relative
  if (-not (Test-Path $full)) {
    Add-Line "[缺失 MISSING] $relative"
    continue
  }
  try {
    $null = Get-Content -Raw -LiteralPath $full | ConvertFrom-Json
    Add-Line "[JSON OK] $relative"
  } catch {
    Add-Line "[JSON错误] $relative : $($_.Exception.Message)"
  }
}

Add-Section "7. 模型文件（名称和大小）"
$ModelsRoot = Join-Path $PackRoot "engine\ComfyUI\models"
if (Test-Path $ModelsRoot) {
  try {
    $modelFiles = Get-ChildItem -LiteralPath $ModelsRoot -Recurse -File -ErrorAction SilentlyContinue |
      Where-Object { $_.Extension -in @(".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin") } |
      Sort-Object FullName
    Add-Line "模型文件数: $($modelFiles.Count)"
    foreach ($file in $modelFiles) {
      $relative = $file.FullName.Substring($ModelsRoot.Length).TrimStart("\")
      Add-Line "$relative`t$([math]::Round($file.Length / 1MB, 1)) MB"
    }
  } catch {
    Add-Line "扫描模型失败: $($_.Exception.Message)"
  }
} else {
  Add-Line "模型目录不存在: engine\ComfyUI\models"
}

Add-Section "8. 端口7777与8888"
foreach ($port in @(7777, 8888)) {
  $found = $false
  try {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
      $found = $true
      $procName = "unknown"
      try {
        $proc = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) { $procName = $proc.ProcessName }
      } catch {}
      Add-Line "端口${port}: LISTENING  PID=$($connection.OwningProcess)  Process=$procName"
    }
  } catch {}
  if (-not $found) {
    Add-Line "端口${port}: 空闲"
  }
}

Add-Section "9. 最近启动日志"
$LogDir = Join-Path $PackRoot "userdata\logs"
if (Test-Path $LogDir) {
  $logs = Get-ChildItem -LiteralPath $LogDir -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 4
  if ($logs) {
    foreach ($log in $logs) {
      Add-Line ""
      Add-Line "--- $($log.Name) | $($log.LastWriteTime) | $($log.Length) bytes ---"
      try {
        Get-Content -LiteralPath $log.FullName -Tail 120 -ErrorAction Stop | ForEach-Object { Add-Line $_ }
      } catch {
        Add-Line "读取日志失败: $($_.Exception.Message)"
      }
    }
  } else {
    Add-Line "日志目录存在，但还没有日志。请先运行一次启动.bat。"
  }
} else {
  Add-Line "还没有日志目录。请先运行一次启动.bat。"
}

Add-Section "10. 给AI的排查提示"
Add-Line "请根据本诊断信息检查："
Add-Line "1. 是否检测到NVIDIA显卡，以及驱动和CUDA是否匹配。"
Add-Line "2. torch.cuda.is_available是否为True。"
Add-Line "3. 关键文件、工作流JSON和模型是否缺失。"
Add-Line "4. 7777或8888是否被其他进程占用。"
Add-Line "5. 最近日志中最早出现的ERROR、Traceback、CUDA或OOM是什么。"
Add-Line "6. 给出适合小白逐步执行的修复方法，不要直接要求重装整个系统。"

try {
  $utf8Bom = New-Object System.Text.UTF8Encoding($true)
  [System.IO.File]::WriteAllLines($OutputFile, $Lines, $utf8Bom)
  Write-Host ""
  Write-Host "诊断完成：" -ForegroundColor Green
  Write-Host $OutputFile -ForegroundColor Cyan
  Write-Host ""
  Write-Host "可以先打开检查，再把TXT文件拖给AI分析。"
  try { Start-Process notepad.exe -ArgumentList "`"$OutputFile`"" } catch {}
  exit 0
} catch {
  Write-Host "[错误] 无法写入诊断文件：$($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
