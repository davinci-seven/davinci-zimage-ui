param(
  [string]$PackRoot = "E:\z-image\release\达芬七-ZImage-一键出图包-v1.4.0",
  [string]$VolumeSize = "3900m",
  [switch]$Force
)

$ErrorActionPreference = "Stop"

if ($VolumeSize -notmatch '^\d+[kKmMgG]$') {
  throw "VolumeSize 格式错误，请使用 3900m、5g、10g 这类写法。"
}

$pack = (Resolve-Path -LiteralPath $PackRoot).Path
$releaseRoot = (Resolve-Path -LiteralPath (Split-Path $pack -Parent)).Path
if (-not $pack.StartsWith($releaseRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "PackRoot 必须是 release 目录下的具体一键出图包。"
}

$seven = @(
  "C:\Program Files\7-Zip\7z.exe",
  "C:\Program Files (x86)\7-Zip\7z.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $seven) {
  $cmd = Get-Command 7z -ErrorAction SilentlyContinue
  if ($cmd) { $seven = $cmd.Source }
}
if (-not $seven) {
  throw "没有找到 7-Zip。请先安装 7-Zip。"
}

$name = Split-Path $pack -Leaf
$archiveBase = Join-Path $releaseRoot "$name.7z"
$partFilter = "$name.7z.*"
$manifest = Join-Path $releaseRoot "$name.sha256.txt"
$guide = Join-Path $releaseRoot "$name-下载与解压说明.txt"

$existing = @(
  Get-ChildItem -LiteralPath $releaseRoot -File -Filter $partFilter -ErrorAction SilentlyContinue
)
foreach ($p in @($manifest, $guide)) {
  if (Test-Path -LiteralPath $p) { $existing += Get-Item -LiteralPath $p }
}
if ($existing.Count -gt 0 -and -not $Force) {
  throw "已存在同名分卷或说明文件。确认重做时加 -Force。"
}
if ($Force) {
  foreach ($p in $existing) {
    if ($p.FullName.StartsWith($releaseRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $p.FullName -Force
    }
  }
}

$sourceBytes = (
  Get-ChildItem -LiteralPath $pack -Recurse -File -ErrorAction Stop |
    Measure-Object Length -Sum
).Sum
$drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($releaseRoot).TrimEnd(":\"))
if ($drive.Free -lt ($sourceBytes + 2GB)) {
  throw ("空间不足：源包约 {0:N2} GB，可用空间只有 {1:N2} GB。" -f ($sourceBytes / 1GB), ($drive.Free / 1GB))
}

Write-Host "========================================"
Write-Host "  达芬七 Z-Image 分卷打包"
Write-Host "========================================"
Write-Host ("源目录：{0}" -f $pack)
Write-Host ("源体积：{0:N2} GB" -f ($sourceBytes / 1GB))
Write-Host ("分卷：  {0}" -f $VolumeSize)
Write-Host "模式：  7z / Store / 非固实"
Write-Host ""

Push-Location $releaseRoot
try {
  & $seven a -t7z -mx=0 -ms=off "-v$VolumeSize" $archiveBase $name
  if ($LASTEXITCODE -ne 0) {
    throw "7-Zip 打包失败，退出码 $LASTEXITCODE。"
  }
}
finally {
  Pop-Location
}

$parts = @(
  Get-ChildItem -LiteralPath $releaseRoot -File -Filter $partFilter |
    Sort-Object Name
)
if ($parts.Count -eq 0) {
  throw "没有生成分卷文件。"
}

Write-Host ""
Write-Host "正在生成 SHA256 校验文件……"
$hashLines = foreach ($part in $parts) {
  $hash = (Get-FileHash -LiteralPath $part.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $($part.Name)"
}
[IO.File]::WriteAllLines($manifest, $hashLines, [Text.UTF8Encoding]::new($false))

$guideLines = @(
  "达芬七 · Z-Image 一键出图包 v1.4.0 下载与解压",
  "",
  "1. 下载全部 .7z.001、.002、.003……分卷，放在同一个文件夹。",
  "2. 安装网盘同目录里的 7-Zip-26.02-x64-官方安装包.exe。",
  "3. 只对 .7z.001 点右键 → 7-Zip → 解压到当前文件夹。",
  "4. 不要单独解压 .002 之后的文件，也不要修改分卷文件名。",
  "5. 下载异常时，双击「双击一键校验下载文件.bat」自动核对全部文件。",
  "   第一次使用请先看「SHA256校验怎么用.txt」。",
  "",
  "解压工具：",
  "· 推荐使用随包提供的 7-Zip 官方安装包。",
  "· Bandizip 也能解压：所有分卷放在一起，只打开 .7z.001。",
  "· 不建议用 Windows 自带解压处理本分卷包。",
  "",
  "作者：达芬七",
  "X：https://x.com/davinci_seven"
)
[IO.File]::WriteAllLines($guide, $guideLines, [Text.UTF8Encoding]::new($false))

$total = ($parts | Measure-Object Length -Sum).Sum
Write-Host ""
Write-Host "==== 完成 ===="
Write-Host ("分卷数量：{0}" -f $parts.Count)
Write-Host ("分卷总计：{0:N2} GB" -f ($total / 1GB))
Write-Host ("校验文件：{0}" -f $manifest)
Write-Host ("解压说明：{0}" -f $guide)
$parts | ForEach-Object {
  Write-Host ("  {0}  {1:N2} GB" -f $_.Name, ($_.Length / 1GB))
}
