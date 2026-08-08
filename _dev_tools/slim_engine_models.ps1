# 只在「已复制出来的发行包」里跑：删掉与 Z-Image 无关的大模型文件。
# 整合包里那份 models 是用户本机全套（flux / 放大 / 分割 / 提示词生成…），
# 不裁的话包会到 97GB，实际出图只用得到 z-image 那几个。
param(
  [Parameter(Mandatory = $true)][string]$EngineRoot,
  [switch]$WhatIf
)
$ErrorActionPreference = "Stop"

# —— 安全闸：绝不允许指向本机在用的引擎 ——
$full = (Resolve-Path $EngineRoot).Path
if ($full -notmatch '\\release') {
  Write-Host "[ERROR] 只能对 release 目录下的引擎副本裁剪，收到：$full"
  exit 1
}
$models = Join-Path $full "ComfyUI\models"
if (-not (Test-Path $models)) { Write-Host "[models] 没有 models 目录，跳过"; exit 0 }

# 保留：出图链路真正会加载的东西（三个档位 + 文本编码器 + VAE + 本包的 LoRA）
$keep = @(
  'diffusion_models\z-image\',
  'diffusion_models\z_image_turbo-Q4_K_M.gguf',
  'text_encoders\z-image\',
  'vae\z-image-qwen.safetensors',
  'loras\zimage\'
)
# 只动大文件：小文件（配置、占位、节点自带的小权重）一律不碰，免得误伤自定义节点
$minMB = 20

$freed = 0L
$kept = 0L
Get-ChildItem -Path $models -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
  $rel = $_.FullName.Substring($models.Length).TrimStart('\')
  $isKeep = $false
  foreach ($k in $keep) { if ($rel.StartsWith($k, 'OrdinalIgnoreCase')) { $isKeep = $true; break } }
  if ($isKeep) { $kept += $_.Length; return }
  if ($_.Length -lt ($minMB * 1MB)) { return }
  $freed += $_.Length
  Write-Host ("[strip model] {0}  ({1:N1} GB)" -f $rel, ($_.Length / 1GB))
  if (-not $WhatIf) { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }
}

if (-not $WhatIf) {
  # 清掉裁空了的目录（保留 put_*_here 占位所在的那些）
  for ($i = 0; $i -lt 3; $i++) {
    Get-ChildItem -Path $models -Recurse -Directory -ErrorAction SilentlyContinue |
      Where-Object { -not (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue) } |
      Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  }
}
Write-Host ("[models] 保留 {0:N1} GB，裁掉 {1:N1} GB" -f ($kept / 1GB), ($freed / 1GB))
