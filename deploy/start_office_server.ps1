$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Virtual environment not found. Create it first with: python -m venv .venv"
}

function Get-OfficeIPv4Address {
    $candidates = @()

    try {
        $candidates = Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object {
                $_.IPAddress -notlike "127.*" -and
                $_.IPAddress -notlike "169.254.*" -and
                $_.PrefixOrigin -ne "WellKnown"
            } |
            Sort-Object -Property InterfaceMetric
    }
    catch {
        $candidates = @()
    }

    $preferred = $candidates |
        Where-Object {
            $_.InterfaceAlias -match "Wi-Fi|Ethernet"
        } |
        Select-Object -First 1

    if ($preferred) {
        return $preferred.IPAddress
    }

    $fallback = $candidates | Select-Object -First 1
    if ($fallback) {
        return $fallback.IPAddress
    }

    $ipconfigOutput = ipconfig
    foreach ($line in $ipconfigOutput) {
        if ($line -match "IPv4 Address[ .]*: (?<ip>\d+\.\d+\.\d+\.\d+)") {
            $ip = $Matches["ip"]
            if ($ip -notlike "127.*" -and $ip -notlike "169.254.*") {
                return $ip
            }
        }
    }

    return $null
}

$officeIp = Get-OfficeIPv4Address
if (-not $officeIp) {
    throw "Could not detect a local IPv4 address. Connect to the office network and try again."
}

$env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost,$officeIp"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "http://127.0.0.1:8000,http://localhost:8000,http://$officeIp`:8000"

Write-Host ""
Write-Host "Office server IP detected: $officeIp" -ForegroundColor Green
Write-Host "Open on this computer: http://127.0.0.1:8000/" -ForegroundColor Cyan
Write-Host "Open on other office computers: http://$officeIp`:8000/" -ForegroundColor Cyan
Write-Host ""

& ".venv\Scripts\python.exe" manage.py migrate
& ".venv\Scripts\python.exe" manage.py collectstatic --noinput
& ".venv\Scripts\python.exe" -m waitress --host=0.0.0.0 --port=8000 config.wsgi:application
