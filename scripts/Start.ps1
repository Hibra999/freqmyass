$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.runtime\env\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath) -or -not (Test-Path 'frontend\dist\index.html')) {
    throw 'Run Setup.cmd first.'
}
try {
    $existing = Invoke-WebRequest 'http://127.0.0.1:8765/' -TimeoutSec 2 -SessionVariable localSession
    $status = Invoke-RestMethod 'http://127.0.0.1:8765/workbench/status' -WebSession $localSession -TimeoutSec 2
    if (-not $status.engine_version) { throw 'Port 8765 is occupied by another application.' }
    Start-Process 'http://127.0.0.1:8765/'
    exit 0
} catch {
    if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Port 8765 is already occupied. Close the other application first.'
    }
}
$env:PYTHONUNBUFFERED = '1'
$env:MPLBACKEND = 'Agg'
$serverProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m uvicorn server.app:app --host 127.0.0.1 --port 8765' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput '.runtime\server.log' -RedirectStandardError '.runtime\server-error.log' -PassThru
$serverProcess.Id | Set-Content '.runtime\server.pid'
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    try { $null = Invoke-WebRequest 'http://127.0.0.1:8765/' -TimeoutSec 1; Start-Process 'http://127.0.0.1:8765/'; exit 0 } catch { }
}
throw 'Startup failed. Read .runtime\server-error.log.'
