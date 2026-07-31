$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$venv = Join-Path $backend ".venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Criando ambiente virtual..."
    python -m venv $venv
    & $python -m pip install --upgrade pip
    & $python -m pip install -r (Join-Path $backend "requirements.txt")
}

if (-not (Test-Path (Join-Path $backend ".env"))) {
    Copy-Item (Join-Path $backend ".env.example") (Join-Path $backend ".env")
    Write-Host ""
    Write-Host "Arquivo .env criado em backend\.env"
    Write-Host "Edite e preencha GEMINI_API_KEY (gratuito) ou ANTHROPIC_API_KEY (pago)."
    Write-Host "Sem chave, o sistema usa o motor mock (dados de exemplo)."
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object {
        $_.IPAddress -ne "127.0.0.1" -and $_.AddressState -eq "Preferred"
    } | Select-Object -First 1).IPAddress

if (-not $ip) { $ip = "localhost" }

Write-Host ""
Write-Host "Servidor subindo..."
Write-Host "No PC:        http://localhost:8000"
Write-Host "No celular:   http://${ip}:8000   (mesma rede Wi-Fi)"
Write-Host ""

& $python -m uvicorn app:app --app-dir $backend --host 0.0.0.0 --port 8000
