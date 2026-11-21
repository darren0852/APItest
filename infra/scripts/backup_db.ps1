param([string]$OutDir = "$PSScriptRoot\backups")
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $OutDir "apiplatform_$timestamp.sql"
docker exec api-platform-db pg_dump -U apidev apiplatform > $outFile
if (Test-Path $outFile) {
    $size = (Get-Item $outFile).Length
    Write-Output "Backup created: $outFile ($([math]::Round($size/1KB,1)) KB)"
    Get-ChildItem $OutDir -Filter "apiplatform_*.sql" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 7 | Remove-Item -Force
} else { Write-Output "Backup FAILED" }