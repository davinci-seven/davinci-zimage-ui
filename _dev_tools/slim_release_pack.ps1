# 清理一键出图包里 Z-Image 前端用不到的引擎文件。
# 不删 Z-Image UNet/VAE/CLIP 与 styles.json 用到的 LoRA。
#
#   powershell -ExecutionPolicy Bypass -File _dev_tools\slim_release_pack.ps1
#   powershell -ExecutionPolicy Bypass -File _dev_tools\slim_release_pack.ps1 -PackRoot "E:\z-image\release\达芬七-ZImage-一键出图包-v1.4.0"

param(
  [string]$PackRoot = "E:\z-image\release\达芬七-ZImage-一键出图包-v1.4.0"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path (Join-Path $PackRoot "engine\ComfyUI\main.py"))) {
  Write-Host "not a full pack: $PackRoot"
  exit 1
}

function GB($bytes) { [math]::Round($bytes / 1GB, 2) }
function DirBytes($p) {
  if (-not (Test-Path $p)) { return 0 }
  (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
}

$before = DirBytes $PackRoot
Write-Host "BEFORE: $(GB $before) GB  $PackRoot"

$eng = Join-Path $PackRoot "engine"
$models = Join-Path $eng "ComfyUI\models"
$freed = 0L

function Kill-Path($rel) {
  $p = if ([IO.Path]::IsPathRooted($rel)) { $rel } else { Join-Path $PackRoot $rel }
  if (-not (Test-Path $p)) { return }
  $sz = DirBytes $p
  Write-Host ("[rm] {0,7:N2} GB  {1}" -f (GB $sz), $rel)
  Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue
  $script:freed += $sz
}

# --- 1) 开发向 / 非用户界面 ---
Kill-Path "tools"
Kill-Path "app\tools"
Kill-Path "QA_CHECKLIST.md"
Kill-Path "RELEASE_NOTES.txt"
Kill-Path "userdata\logs"      # QA/启动日志可能包含本机路径、显卡与用户名

# --- 2) 旧整合包壳子（我们只用 Comfy API + 自己的 Gradio）---
@(
  "engine\tab",
  "engine\api",
  "engine\modules",
  "engine\components",
  "engine\ui",
  "engine\scripts",
  "engine\templates",
  "engine\data_utils",
  "engine\data",
  "engine\git",
  "engine\assets",
  "engine\models",          # 翻译等，UI 不用
  "engine\input",
  "engine\temp",
  "engine\.cache",
  "engine\app.py",
  "engine\run_cpu.bat",
  "engine\run_nvidia_gpu.bat",
  "engine\run_nvidia_gpu_fast_fp16_accumulation.bat",
  "engine\z-image.lnk",
  "engine\启动器.bat"
) | ForEach-Object { Kill-Path $_ }

# --- 3) 禁用的 custom_nodes 整夹扔掉（要恢复从开发引擎拷）---
Kill-Path "engine\ComfyUI\custom_nodes\.disabled"

# --- 4) 非 Z-Image 模型目录 ---
$dropModelDirs = @(
  "prompt_generator",
  "FlashVSR-v1.1",
  "SEEDVR2",
  "model_patches",
  "clip",              # Z-Image 用 text_encoders\qwen
  "clip_vision",
  "sams", "sam2", "onnx", "rembg", "ultralytics",
  "style_models", "upscale_models", "interpolation",
  "ipadapter", "photomaker", "pulid",
  "diffusers", "controlnet", "checkpoints",
  "audio_encoders", "embeddings", "hypernetworks", "gligen",
  "latent_upscale_models", "unet", "vae_approx", "configs"
)
foreach ($d in $dropModelDirs) {
  Kill-Path (Join-Path "engine\ComfyUI\models" $d)
}

# flux 等非 Z-Image 扩散
Kill-Path "engine\ComfyUI\models\diffusion_models\flux1"
# GGUF 文本编码器用不到（defaults 用 safetensors qwen）
$ggufClip = Join-Path $models "text_encoders\qwen3-4b-q4_k_m.gguf"
if (Test-Path $ggufClip) {
  $sz = (Get-Item $ggufClip).Length
  Write-Host ("[rm] {0,7:N2} GB  text_encoders\qwen3-4b-q4_k_m.gguf" -f (GB $sz))
  Remove-Item $ggufClip -Force
  $freed += $sz
}

# --- 5) 只保留 styles.json 引用的 LoRA ---
$stylesJson = Join-Path $PackRoot "assets\styles\styles.json"
$lorasRoot = Join-Path $models "loras"
if ((Test-Path $stylesJson) -and (Test-Path $lorasRoot)) {
  $styles = (Get-Content $stylesJson -Raw -Encoding UTF8 | ConvertFrom-Json).styles
  $needNames = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
  foreach ($s in $styles) {
    $fn = [IO.Path]::GetFileName(($s.file -replace '\\','/'))
    [void]$needNames.Add($fn)
  }
  Get-ChildItem $lorasRoot -Recurse -File -Include *.safetensors,*.pt,*.ckpt -ErrorAction SilentlyContinue | ForEach-Object {
    if (-not $needNames.Contains($_.Name)) {
      $sz = $_.Length
      Write-Host ("[rm lora] {0,7:N2} GB  {1}" -f (GB $sz), $_.FullName.Substring($lorasRoot.Length+1))
      Remove-Item $_.FullName -Force
      $freed += $sz
    }
  }
  # 空目录 flux1 等
  Get-ChildItem $lorasRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $left = Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue
    if (-not $left) {
      Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
      Write-Host "[rm empty] loras\$($_.Name)"
    }
  }
}

# --- 6) Comfy 测试/文档/输出 ---
@(
  "engine\ComfyUI\tests",
  "engine\ComfyUI\tests-unit",
  "engine\ComfyUI\script_examples",
  "engine\ComfyUI\output",
  "engine\ComfyUI\.ci"
) | ForEach-Object { Kill-Path $_ }

# --- 7) 便携 Python 只保留运行时，去掉测试/文档/编译开发文件 ---
# 这些文件不会参与达芬七固定工作流出图，却会让机械硬盘/U 盘一次复制数万个小文件。
$pyRoot = Join-Path $eng "python"
$sitePackages = Join-Path $pyRoot "Lib\site-packages"

@(
  "engine\python\Lib\test",                                      # Python 标准库测试
  "engine\python\include",                                       # Python C 扩展开发头文件
  "engine\python\libs",                                          # Python C 扩展链接库
  "engine\python\Lib\site-packages\comfyui_embedded_docs",        # Comfy 节点内嵌说明，网页壳不用
  "engine\python\Lib\site-packages\comfyui_embedded_docs-0.3.1.dist-info",
  "engine\python\Lib\site-packages\cmake",                        # 编译扩展用，固定推理不需要
  "engine\python\Lib\site-packages\cmake-4.1.2.dist-info",
  "engine\python\Lib\site-packages\torch\include"                 # PyTorch C++ 扩展开发头文件
) | ForEach-Object { Kill-Path $_ }

# 不把版本号写死：补删相同包名的 dist-info。
if (Test-Path $sitePackages) {
  Get-ChildItem $sitePackages -Directory -ErrorAction SilentlyContinue |
    Where-Object {
      $_.Name -like "comfyui_embedded_docs-*.dist-info" -or
      $_.Name -like "cmake-*.dist-info"
    } |
    ForEach-Object { Kill-Path $_.FullName }

  # 第三方包自带 tests/test。只取最外层目录，避免重复遍历/计数。
  $testDirs = Get-ChildItem $sitePackages -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object {
      $_.Name -in @("test", "tests") -and
      # NumPy 正常导入链会引用 numpy._core.tests._natype，并非只在跑测试时使用。
      $_.FullName -ne (Join-Path $sitePackages "numpy\_core\tests")
    } |
    Sort-Object { $_.FullName.Length }
  $selectedTests = New-Object System.Collections.Generic.List[System.IO.DirectoryInfo]
  foreach ($d in $testDirs) {
    $nested = $false
    foreach ($parent in $selectedTests) {
      if ($d.FullName.StartsWith($parent.FullName + "\", [StringComparison]::OrdinalIgnoreCase)) {
        $nested = $true
        break
      }
    }
    if (-not $nested) { $selectedTests.Add($d) }
  }
  foreach ($d in $selectedTests) { Kill-Path $d.FullName }
}

# torch\lib 里的 DLL 是推理运行时；同目录的 .lib 仅供开发者链接 C++ 扩展。
$torchLib = Join-Path $sitePackages "torch\lib"
if (Test-Path $torchLib) {
  Get-ChildItem $torchLib -File -Filter "*.lib" -ErrorAction SilentlyContinue | ForEach-Object {
    $sz = $_.Length
    Write-Host ("[rm devlib] {0,7:N2} GB  {1}" -f (GB $sz), $_.Name)
    Remove-Item -LiteralPath $_.FullName -Force
    $freed += $sz
  }
}

# CMake 的命令入口可能同时装在 Scripts。
Get-ChildItem (Join-Path $pyRoot "Scripts") -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like "cmake*" -or $_.Name -like "ctest*" -or $_.Name -like "cpack*" } |
  ForEach-Object {
    $sz = $_.Length
    Write-Host "[rm build-tool] $($_.FullName.Substring($PackRoot.Length + 1))"
    Remove-Item -LiteralPath $_.FullName -Force
    $freed += $sz
  }

# 重建空 output/input/temp
foreach ($d in @("output","input","temp")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $eng "ComfyUI\$d") | Out-Null
}
New-Item -ItemType Directory -Force -Path (Join-Path $PackRoot "userdata\logs") | Out-Null

# pycache（全包，包括 Python 与 App）
Get-ChildItem $PackRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$after = DirBytes $PackRoot
Write-Host ""
Write-Host "==== SLIM DONE ===="
Write-Host "Freed ~ $(GB $freed) GB (this run accounting)"
Write-Host "BEFORE $(GB $before) GB → AFTER $(GB $after) GB"
Write-Host "Keep: Z-Image FP8/GGUF/BF16 + qwen + vae + 风格 LoRA + 精简 custom_nodes"
