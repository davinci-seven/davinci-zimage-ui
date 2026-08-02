# Download popular Z-Image Turbo LoRAs via CivitAI API
# Usage:
#   $env:CIVITAI_API_TOKEN = "your_token"
#   powershell -ExecutionPolicy Bypass -File tools\download_top_loras.ps1

$ErrorActionPreference = "Stop"
$token = $env:CIVITAI_API_TOKEN
if (-not $token) {
  # fallback: read from fetch_civitai_loras.md if user embedded it
  Write-Host "Set CIVITAI_API_TOKEN first."
  exit 1
}
$dest = Join-Path $PSScriptRoot "..\..\ComfyUI-zimage\ComfyUI\models\loras\zimage"
if (-not (Test-Path $dest)) {
  $dest = "e:\z-image\ComfyUI-zimage\ComfyUI\models\loras\zimage"
}
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$headers = @{ Authorization = "Bearer $token" }

$modelIds = @(2185167, 2234266, 2215818, 2334593, 2209262, 2268008, 580857, 667086)
foreach ($id in $modelIds) {
  try {
    $m = Invoke-RestMethod -Uri "https://civitai.com/api/v1/models/$id" -Headers $headers -TimeoutSec 60
    $ver = $null
    foreach ($v in $m.modelVersions) {
      if ($v.baseModel -match "ZImage") { $ver = $v; break }
    }
    if (-not $ver) { Write-Host "skip $id"; continue }
    $file = ($ver.files | Where-Object { $_.name -like "*.safetensors" } | Select-Object -First 1)
    if (-not $file) { continue }
    $safe = ($file.name -replace "[^\w\.\-]+", "_")
    $out = Join-Path $dest $safe
    if (Test-Path $out) { Write-Host "exists $safe"; continue }
    Write-Host "DL $($m.name) -> $safe"
    & curl.exe -L --fail -H "Authorization: Bearer $token" -o $out "https://civitai.com/api/download/models/$($ver.id)"
  } catch {
    Write-Host "ERR $id $_"
  }
}
Write-Host "done -> $dest"
