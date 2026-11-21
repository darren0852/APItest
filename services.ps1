param([string]$Action = "start")

function Start-ServiceStack {
    $docker = docker ps --format "{{.Names}}" 2>$null
    if ($docker -notmatch "api-platform-db") {
        Set-Location "$PSScriptRoot\infra"
        docker compose --profile dev up -d
        Set-Location $PSScriptRoot
    }

    if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
        $env:PYTHONIOENCODING = "utf-8"
        $env:ENABLE_INTERNAL_MOCK = "true"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c","cd /d $PSScriptRoot\apps\api && python -m uvicorn main:app --port 8000" -WindowStyle Minimized
        Start-Sleep -Seconds 6
    }

    if (-not (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)) {
        Set-Location "$PSScriptRoot\apps\web"
        if (-not (Test-Path node_modules)) { npm install }
        npm run build
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c","cd /d $PSScriptRoot\apps\web && npm run start" -WindowStyle Hidden
        Set-Location $PSScriptRoot
        Start-Sleep -Seconds 6
    }

    Write-Output "All services running."
}

function Stop-Port([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

switch ($Action) {
    "start" { Start-ServiceStack }
    "restart-api" {
        Stop-Port 8000
        $env:PYTHONIOENCODING = "utf-8"
        $env:ENABLE_INTERNAL_MOCK = "true"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c","cd /d $PSScriptRoot\apps\api && python -m uvicorn main:app --port 8000" -WindowStyle Minimized
        Start-Sleep -Seconds 6
        Write-Output "FastAPI restarted."
    }
    "restart-web" {
        Stop-Port 3000
        Set-Location "$PSScriptRoot\apps\web"
        npm run build
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c","cd /d $PSScriptRoot\apps\web && npm run start" -WindowStyle Hidden
        Set-Location $PSScriptRoot
        Start-Sleep -Seconds 6
        Write-Output "Next.js restarted."
    }
    "status" {
        foreach ($port in 3000,8000,9000) {
            $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
            if ($connection) { Write-Output "Port $port : UP" } else { Write-Output "Port $port : DOWN" }
        }
    }
}
