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
    $modelFolder = Join-Path $projectRoot 'models'
    $modelPath = Join-Path $modelFolder 'hand_landmarker.task'
    if (-not (Test-Path -LiteralPath $modelPath)) {
        New-Item -ItemType Directory -Force -Path $modelFolder | Out-Null
        Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task' -OutFile $modelPath
        $modelSize = (Get-Item -LiteralPath $modelPath).Length
        if ($modelSize -lt 100000 -or $modelSize -gt 20000000) { throw 'Unexpected hand model size.' }
    }
} finally { Pop-Location }
