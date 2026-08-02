# 精简 Comfy 自定义节点：只留 Z-Image 傻瓜包用到的
# 旧整合包里视频/ControlNet/LLM/提示词小助手等会拖慢冷启动，移到 .disabled/
#
#   powershell -ExecutionPolicy Bypass -File tools\slim_engine_nodes.ps1
#   powershell -ExecutionPolicy Bypass -File tools\slim_engine_nodes.ps1 -Restore
#   powershell -ExecutionPolicy Bypass -File tools\slim_engine_nodes.ps1 -EngineRoot "E:\path\to\engine"

param(
  [switch]$Restore,
  [string]$EngineRoot = ""
)

$ErrorActionPreference = "Stop"
$PackRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not $EngineRoot) {
  if (Test-Path (Join-Path $PackRoot "engine\ComfyUI\custom_nodes")) {
    $EngineRoot = Join-Path $PackRoot "engine"
  } elseif (Test-Path (Join-Path (Split-Path $PackRoot -Parent) "ComfyUI-zimage\ComfyUI\custom_nodes")) {
    $EngineRoot = Join-Path (Split-Path $PackRoot -Parent) "ComfyUI-zimage"
  } else {
    Write-Host "engine not found"
    exit 1
  }
}

$cn = Join-Path $EngineRoot "ComfyUI\custom_nodes"
$dis = Join-Path $cn ".disabled"
if (-not (Test-Path $cn)) { Write-Host "no custom_nodes at $cn"; exit 1 }
New-Item -ItemType Directory -Force -Path $dis | Out-Null

# 工作流依赖：GGUF、基础工具、创造性；LoRA 走原生 LoraLoader
$keep = @(
  "ComfyUI-GGUF",
  "comfyui_essentials",
  "rgthree-comfy",
  "SeedVarianceEnhancer"
)

$listFile = Join-Path $dis "_davinci_disabled_list.txt"

if ($Restore) {
  if (-not (Test-Path $listFile)) {
    Write-Host "no list at $listFile — restore manually from .disabled\"
    exit 1
  }
  Get-Content $listFile | ForEach-Object {
    $name = $_.Trim()
    if (-not $name) { return }
    $src = Join-Path $dis $name
    $dst = Join-Path $cn $name
    if ((Test-Path $src) -and -not (Test-Path $dst)) {
      Move-Item -LiteralPath $src -Destination $dst -Force
      Write-Host "[restore] $name"
    }
  }
  Write-Host "done restore"
  exit 0
}

$preferDisable = @(
  "ComfyUI-Manager",
  "comfyui_memory_cleanup",
  "comfyui-custom-scripts",
  "prompt-assistant",
  "llm-toolkit",
  "vertex-ai-comfyui-nodes",
  "comfyui_controlnet_aux",
  "ComfyUI-WanVideoWrapper",
  "ComfyUI-WanAnimatePreprocess",
  "ComfyUI-WanMoeKSampler",
  "wanblockswap",
  "comfyui-videohelpersuite",
  "comfyui-frame-interpolation",
  "ComfyUI-GIMM-VFI",
  "ComfyUI-FlashVSR_Ultra_Fast",
  "seedvr2_videoupscaler",
  "comfyui-mixlab-nodes",
  "comfyui_layerstyle",
  "RES4LYF",
  "LanPaint",
  "was-ns",
  "comfyui-kjnodes",
  "comfyui-supir",
  "comfyui-impact-pack",
  "comfyui-impact-subpack",
  "comfyui-advanced-controlnet",
  "comfyui_ttp_toolset",
  "Comfyui-SecNodes",
  "qweneditutils",
  "ComfyUI_Comfyroll_CustomNodes",
  "comfyui-easy-use",
  "comfyui-inpaint-cropandstitch",
  "comfyui-rmbg",
  "comfyui-various",
  "ComfyUI-Crystools",
  "cg-use-everywhere",
  "ComfyUI-DD-Translation"
)

$moved = @()
foreach ($name in $preferDisable) {
  $src = Join-Path $cn $name
  if (-not (Test-Path $src)) { continue }
  $dst = Join-Path $dis $name
  if (Test-Path $dst) {
    Write-Host "[skip already] $name"
    continue
  }
  Move-Item -LiteralPath $src -Destination $dst -Force
  $moved += $name
  Write-Host "[disable] $name"
}

if ($moved.Count -gt 0) {
  # append unique
  $prev = @()
  if (Test-Path $listFile) { $prev = Get-Content $listFile }
  ($prev + $moved) | Select-Object -Unique | Set-Content $listFile -Encoding UTF8
}

Write-Host ""
Write-Host "Engine: $EngineRoot"
Write-Host "Active nodes:"
Get-ChildItem $cn -Directory | Where-Object { $_.Name -notlike ".*" } | ForEach-Object { "  - $($_.Name)" }
Write-Host ""
Write-Host "Restart 启动.bat to feel faster cold start."
Write-Host "Restore later: -Restore"
