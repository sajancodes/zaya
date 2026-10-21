$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & .\.venv\Scripts\python.exe -m venv .venv-hands
    if ($LASTEXITCODE -ne 0) { throw 'Optional hand environment creation failed.' }
    & .\.venv-hands\Scripts\python.exe -m pip install -r requirements-hands.txt
    if ($LASTEXITCODE -ne 0) { throw 'Optional hand dependencies failed.' }
    & .\.venv-hands\Scripts\python.exe -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Optional hand dependency check failed.' }
} finally { Pop-Location }
