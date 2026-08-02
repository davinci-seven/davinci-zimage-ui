# 达芬七 Z-Image 发行打包
#
# UI 轻量包（默认）:
#   powershell -ExecutionPolicy Bypass -File _dev_tools\make_release_pack.ps1
#
# 完整一键出图包（含 engine / 模型，几十 GB）:
#   powershell -ExecutionPolicy Bypass -File _dev_tools\make_release_pack.ps1 -FullBundle
#
# 完整包 + 尝试 7z 压缩（可选，很慢）:
#   powershell -ExecutionPolicy Bypass -File _dev_tools\make_release_pack.ps1 -FullBundle -Zip

param(
  [switch]$IncludeEngine,   # 兼容旧参数
  [switch]$FullBundle,      # 推荐：完整一键出图包
  [switch]$Zip,             # 完整包默认不 zip；加此开关才压
  [string]$OutRoot = ""
)

$ErrorActionPreference = "Stop"
$PackRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Version = "1.4.0"
$Stamp = Get-Date -Format "yyyyMMdd"
if (-not $OutRoot) {
  $OutRoot = Join-Path (Split-Path $PackRoot -Parent) "release"
}
$wantEngine = $FullBundle -or $IncludeEngine
if ($wantEngine) {
  $DestName = "达芬七-ZImage-一键出图包-v$Version"
} else {
  $DestName = "达芬七-ZImage-UI-v$Version"
}
$Dest = Join-Path $OutRoot $DestName
$Scratch = Join-Path $PackRoot "_dev_scratch"

Write-Host "Pack root : $PackRoot"
Write-Host "Dest      : $Dest"
Write-Host "Mode      : $(if ($wantEngine) { 'FULL BUNDLE + engine' } else { 'UI only' })"
Write-Host "Scratch   : $Scratch"
Write-Host ""

# ---------- 1) Isolate temp/auto files in dev tree ----------
New-Item -ItemType Directory -Force -Path $Scratch | Out-Null
$movePatterns = @(
  "tmp_civit*.json",
  "_bat_*.txt",
  "tmp_*.json"
)
foreach ($pat in $movePatterns) {
  Get-ChildItem -Path $PackRoot -File -Filter $pat -ErrorAction SilentlyContinue | ForEach-Object {
    $target = Join-Path $Scratch $_.Name
    Write-Host "[isolate] $($_.Name)"
    Move-Item -LiteralPath $_.FullName -Destination $target -Force
  }
}

Get-ChildItem -Path $PackRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
  Write-Host "[rm] $($_.FullName.Substring($PackRoot.Length))"
  Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

# ---------- 2) Fresh dest ----------
if (Test-Path $Dest) {
  Write-Host "[clean] remove old $Dest"
  Remove-Item -LiteralPath $Dest -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null

function Copy-Tree($src, $dst) {
  if (-not (Test-Path $src)) { return }
  New-Item -ItemType Directory -Force -Path $dst | Out-Null
  Copy-Item -Path (Join-Path $src "*") -Destination $dst -Recurse -Force
}

# ---------- 3) Copy product files（仅面向最终用户）----------
# 不拷 tools/、_dev_tools/、开发脚本 — 下载 LoRA / 封面 / 打包都只在开发树
Copy-Tree (Join-Path $PackRoot "app") (Join-Path $Dest "app")
Copy-Tree (Join-Path $PackRoot "assets") (Join-Path $Dest "assets")

Copy-Item (Join-Path $PackRoot "启动.bat") $Dest -Force
if (Test-Path (Join-Path $PackRoot "THIRD_PARTY.md")) {
  Copy-Item (Join-Path $PackRoot "THIRD_PARTY.md") $Dest -Force
}
# 不拷：QA_CHECKLIST / RELEASE_NOTES / 生态笔记 / 打包说明（开发向）

# ---------- 4) Strip non-user surface ----------
Get-ChildItem -Path $Dest -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 开发用封面生成 / 风格脚本不进用户包
$appTools = Join-Path $Dest "app\tools"
if (Test-Path $appTools) {
  Write-Host "[strip] app\tools (dev only)"
  Remove-Item -LiteralPath $appTools -Recurse -Force
}
$unusedAppFiles = @("app\core\civitai.py")
foreach ($rel in $unusedAppFiles) {
  $p = Join-Path $Dest $rel
  if (Test-Path $p) {
    Write-Host "[strip] $rel (not used by the offline UI)"
    Remove-Item -LiteralPath $p -Force
  }
}

# 确保没有 tools 目录（误拷时清掉）
$toolsDir = Join-Path $Dest "tools"
if (Test-Path $toolsDir) {
  Write-Host "[strip] tools\ (dev only)"
  Remove-Item -LiteralPath $toolsDir -Recurse -Force
}
foreach ($devDoc in @("QA_CHECKLIST.md", "RELEASE_NOTES.txt", "打包发行说明.md", "生态与更新笔记.md")) {
  $p = Join-Path $Dest $devDoc
  if (Test-Path $p) {
    Write-Host "[strip] $devDoc"
    Remove-Item $p -Force
  }
}

$stylesJson = Join-Path $Dest "assets\styles\styles.json"
$coversDir = Join-Path $Dest "assets\styles\covers"
$needed = New-Object 'System.Collections.Generic.HashSet[string]'
foreach ($n in @("default_card.jpg", "default.jpg", "default.png", "placeholder.png", "_placeholder.png")) {
  [void]$needed.Add($n)
}
if (Test-Path $stylesJson) {
  $styles = (Get-Content $stylesJson -Raw -Encoding UTF8 | ConvertFrom-Json).styles
  foreach ($s in $styles) {
    if ($s.cover) { [void]$needed.Add([IO.Path]::GetFileName($s.cover)) }
    [void]$needed.Add("$($s.id).jpg")
  }
}
Get-ChildItem $coversDir -File -ErrorAction SilentlyContinue | ForEach-Object {
  if (-not $needed.Contains($_.Name)) {
    Write-Host "[strip cover] $($_.Name)"
    Remove-Item $_.FullName -Force
  }
}

$legacyPrompt = Join-Path $Dest "assets\prompts\portrait_presets.json"
if (Test-Path $legacyPrompt) {
  Remove-Item $legacyPrompt -Force
}

# empty runtime dirs — no secrets / no user history
$ud = Join-Path $Dest "userdata"
New-Item -ItemType Directory -Force -Path (Join-Path $ud "gallery") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ud "exports") | Out-Null
@(
  "用户数据目录",
  "· gallery/   图库",
  "· exports/   导出副本",
  "· settings.yaml / favorites.json 首次使用后自动生成",
  "· 设置里可改文件名前缀（默认 davincilab）"
) | Set-Content (Join-Path $ud "README.txt") -Encoding UTF8

# ---------- 5) README ----------
if ($wantEngine) {
  $readme = @"
========================================
  达芬七 · Z-Image  一键出图包 v$Version
  本地一键出图 · 含引擎与模型
========================================

作者：达芬七
X：https://x.com/davinci_seven

----------------------------------------
一、怎么用（本包自带引擎）
----------------------------------------
1. 解压/拷贝整个文件夹到尽量短的路径
   例如 D:\DavinciZImage\
2. 双击「启动.bat」
3. 浏览器打开 http://127.0.0.1:8888
4. 等顶部「引擎 在线」→ 写提示词 → 选风格 → 生成

本包结构：
  启动.bat / app / assets / userdata
  engine\          ← ComfyUI + Python + 模型

----------------------------------------
二、端口
----------------------------------------
· 界面  8888
· 引擎  7777

----------------------------------------
三、模型档位
----------------------------------------
· 标准 FP8（推荐）
· 极低显存 GGUF
· 高质量 BF16（更吃显存）

----------------------------------------
四、你的数据 / 文件名
----------------------------------------
· 图库   userdata\gallery\
· 导出   userdata\exports\
· 设置   userdata\settings.yaml
· 文件名前缀：设置页可改，默认 davincilab
  （例：davincilab_00001_.png；GGUF 会带 _GGUF）

----------------------------------------
五、常见问题
----------------------------------------
Q: 引擎离线？
A: 第一次启动会加载模型，多等一会儿；查杀毒；确认 8888/7777 空闲。

Q: 停止后显存还没释放？
A: 展开「高级设置（可选）」→ 点「释放显存」。下次生成会重新加载模型。

Q: 8G 显存怎么选？
A: 先用「标准 FP8」和一个风格；仍然吃紧再切「极低显存 GGUF」。

Q: 想改输出文件名前缀？
A: 打开「设置」→ 文件名前缀，填 zimage / davincilab 等后回车。

========================================
更新与交流 → X @davinci_seven
========================================
"@
} else {
  $readme = @"
========================================
  达芬七 · Z-Image  UI v$Version
  （仅前端；引擎需另放）
========================================

完整离线请用「一键出图包」版本，或本目录旁放置 ComfyUI-zimage。

作者：达芬七  https://x.com/davinci_seven

1. 引擎：..\ComfyUI-zimage\ 或本目录 engine\
2. 双击 启动.bat
3. http://127.0.0.1:8888

文件名前缀默认 davincilab，可在「设置」里改。
"@
}
[System.IO.File]::WriteAllText((Join-Path $Dest "README.txt"), $readme, [System.Text.UTF8Encoding]::new($false))
# 不写 RELEASE_NOTES 进用户包（开发向）

# ---------- 6) engine ----------
if ($wantEngine) {
  $engineSrc = Join-Path (Split-Path $PackRoot -Parent) "ComfyUI-zimage"
  if (-not (Test-Path (Join-Path $engineSrc "ComfyUI\main.py"))) {
    Write-Host "[ERROR] engine not found at $engineSrc"
    exit 1
  }
  Write-Host "[engine] robocopy from $engineSrc (large copy, please wait)..."
  $eng = Join-Path $Dest "engine"
  New-Item -ItemType Directory -Force -Path $eng | Out-Null
  & robocopy $engineSrc $eng /E /COPY:DAT /R:2 /W:3 /XD output temp user .cache __pycache__ .pytest_cache .vscode .git .github .launcher screenshots tests tests-unit /XF *.log *.pyc *.pyo *.map /NFL /NDL /NP
  $rc = $LASTEXITCODE
  Write-Host "[engine] robocopy exit $rc (0-7 = success bands)"
  if ($rc -ge 8) {
    Write-Host "[ERROR] robocopy failed"
    exit $rc
  }
  # 空 runtime 目录，避免 Comfy 缺路径
  foreach ($d in @("output", "input", "temp")) {
    $p = Join-Path $eng "ComfyUI\$d"
    New-Item -ItemType Directory -Force -Path $p | Out-Null
  }
  # 再扫一层 pycache
  Get-ChildItem -Path $eng -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

  # 去掉旧整合包博主痕迹（界面不需要的文件）
  $brandJunk = @(
    "python\bilibili@秋葉aaaki.txt",
    "git\bilibili@秋葉aaaki.txt",
    "assets\images\other\wechat_pay.jpg",
    "components\support_author.html",
    "components\support_author.py",
    "z-image.lnk"
  )
  foreach ($rel in $brandJunk) {
    $bp = Join-Path $eng $rel
    if (Test-Path $bp) {
      Write-Host "[strip brand] $rel"
      Remove-Item -LiteralPath $bp -Force -ErrorAction SilentlyContinue
    }
  }

  # 旧壳、测试素材和本产品不用的接口层不进发行包
  foreach ($rel in @(
      "core",
      "config",
      ".app_path",
      "ComfyUI\input\ref_img.jpg",
      "ComfyUI\input\ref-image.jpg"
    )) {
    $p = Join-Path $eng $rel
    if (Test-Path $p) {
      Write-Host "[strip unused] $rel"
      Remove-Item -LiteralPath $p -Recurse -Force
    }
  }

  # 精简 custom_nodes（提示词小助手 / 视频 / ControlNet 等）
  $slim = Join-Path $PackRoot "_dev_tools\slim_engine_nodes.ps1"
  if (-not (Test-Path $slim)) { $slim = Join-Path $PackRoot "tools\slim_engine_nodes.ps1" }
  if (Test-Path $slim) {
    Write-Host "[engine] slim custom_nodes..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $slim -EngineRoot $eng
    $disabled = Join-Path $eng "ComfyUI\custom_nodes\.disabled"
    if (Test-Path $disabled) {
      Remove-Item -LiteralPath $disabled -Recurse -Force
    }
  }

  Write-Host "[engine] ready under $eng"
}

# ---------- 7) zip（完整包默认跳过）----------
$zipPath = $null
$doZip = (-not $wantEngine) -or $Zip
if ($doZip) {
  $zipPath = Join-Path $OutRoot "$DestName-$Stamp.zip"
  if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
  # 优先 7z（大包更稳）
  $seven = $null
  foreach ($c in @(
      "${env:ProgramFiles}\7-Zip\7z.exe",
      "${env:ProgramFiles(x86)}\7-Zip\7z.exe",
      "7z"
    )) {
    if ($c -eq "7z") {
      $cmd = Get-Command 7z -ErrorAction SilentlyContinue
      if ($cmd) { $seven = $cmd.Source; break }
    } elseif (Test-Path $c) { $seven = $c; break }
  }
  if ($seven -and $wantEngine) {
    Write-Host "[zip] 7z → $zipPath (large, slow)..."
    & $seven a -tzip -mx=1 $zipPath $Dest
  } else {
    Write-Host "[zip] Compress-Archive → $zipPath"
    Compress-Archive -Path $Dest -DestinationPath $zipPath -CompressionLevel Optimal
  }
} else {
  Write-Host "[zip] skipped for full bundle (folder is the deliverable). Use -Zip if needed."
}

function DirSizeGB($p) {
  if (-not (Test-Path $p)) { return 0 }
  [math]::Round(((Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB), 2)
}

Write-Host ""
Write-Host "==== DONE ===="
Write-Host "Folder : $Dest  ($(DirSizeGB $Dest) GB)"
if ($zipPath -and (Test-Path $zipPath)) {
  Write-Host "Zip    : $zipPath  ($([math]::Round((Get-Item $zipPath).Length/1GB,2)) GB)"
}
Write-Host "Dev junk isolated under: $Scratch"
Write-Host ""
if ($wantEngine) {
  Write-Host "网盘：上传整个文件夹，或用 7-Zip/WinRAR 自己分卷。"
  Write-Host "测试：解压到新路径 → 双击 启动.bat（应自动用 engine\）"
}
