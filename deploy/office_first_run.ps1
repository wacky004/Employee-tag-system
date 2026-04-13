$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env created from .env.example. The office startup script can now auto-detect the current local IP when the server starts."
}

& ".venv\Scripts\python.exe" manage.py migrate
& ".venv\Scripts\python.exe" manage.py collectstatic --noinput
Write-Host "First-run setup complete."
