$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$envPath = Join-Path $projectRoot '.runtime\env'
if (-not (Test-Path (Join-Path $envPath 'python.exe'))) {
    conda create --prefix $envPath python=3.13 pip --yes
    if ($LASTEXITCODE) { throw 'Conda environment creation failed.' }
}
& (Join-Path $envPath 'python.exe') -m pip install -r requirements.txt
if ($LASTEXITCODE) { throw 'Python dependency installation failed.' }
& (Join-Path $envPath 'python.exe') scripts\import_strategies.py
if ($LASTEXITCODE) { throw 'Strategy integrity check failed.' }
Push-Location frontend
try {
    pnpm install --frozen-lockfile
    if ($LASTEXITCODE) { throw 'Frontend installation failed.' }
    pnpm build
    if ($LASTEXITCODE) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Host 'Setup complete. Open Start.cmd, then Market data > Import all to fetch the complete dataset.'
