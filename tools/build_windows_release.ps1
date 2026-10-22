<#
.SYNOPSIS
    Builds the production Windows desktop distribution for Zaya.
    Produces:
      - dist/windows/Zaya/ (onedir application distribution)
      - dist/windows/Zaya-Setup.exe (Inno Setup installer)
      - dist/windows/desktop-update.json (signed/hashed update manifest)
#>
[CmdletBinding()]
param(
    [switch]$SkipRendererBuild,
    [switch]$SkipWorkerBuild,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    Write-Host "=== Zaya Windows Desktop Distribution Build ===" -ForegroundColor Cyan
    Write-Host "Repository root: $repoRoot"

    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $venvPyinstaller = Join-Path $repoRoot ".venv\Scripts\pyinstaller.exe"
    $handsPython = Join-Path $repoRoot ".venv-hands\Scripts\python.exe"
    $handsPyinstaller = Join-Path $repoRoot ".venv-hands\Scripts\pyinstaller.exe"

    if (-not (Test-Path $venvPython)) {
        throw "Main Python environment not found at $venvPython"
    }

    # 1. Spatial renderer build (Vite/Three.js frontend)
    $rendererDir = Join-Path $repoRoot "spatial_renderer"
    $rendererDist = Join-Path $rendererDir "dist"
    if (-not $SkipRendererBuild) {
        if (Test-Path (Join-Path $rendererDir "package.json")) {
            Write-Host "`n[1/5] Building spatial renderer frontend..." -ForegroundColor Yellow
            $npm = Get-Command npm -ErrorAction SilentlyContinue
            if ($npm) {
                Push-Location $rendererDir
                try {
                    if (-not (Test-Path "node_modules")) {
                        Write-Host "Running npm install..."
                        & npm install --no-audit --no-fund
                    }
                    Write-Host "Running npm run build..."
                    & npm run build
                    if ($LASTEXITCODE -ne 0) { throw "Renderer npm build failed." }
                } finally {
                    Pop-Location
                }
            } else {
                Write-Warning "npm not found in PATH; skipping renderer compilation. Existing dist will be used if present."
            }
        }
    } else {
        Write-Host "`n[1/5] Skipping spatial renderer build (-SkipRendererBuild)" -ForegroundColor DarkGray
    }

    # Verify renderer dist exists
    if (-not (Test-Path (Join-Path $rendererDist "index.html"))) {
        Write-Warning "spatial_renderer/dist/index.html not found. Creating placeholder or check renderer build."
    }

    # 2. Build isolated hand tracking worker executable (ZayaHandWorker.exe)
    $distWindows = Join-Path $repoRoot "dist\windows"
    $workerOutDir = Join-Path $distWindows "worker"
    $workerExe = Join-Path $workerOutDir "ZayaHandWorker.exe"

    if (-not $SkipWorkerBuild) {
        Write-Host "`n[2/5] Building isolated hand tracking worker (ZayaHandWorker.exe)..." -ForegroundColor Yellow
        $workerPython = if (Test-Path $handsPython) { $handsPython } else { $venvPython }
        $workerPyinstaller = if (Test-Path $handsPyinstaller) { $handsPyinstaller } else { $venvPyinstaller }

        if (-not (Test-Path $workerPyinstaller)) {
            Write-Warning "PyInstaller not found in $workerPyinstaller; installing into worker environment..."
            & $workerPython -m pip install --quiet pyinstaller
        }

        & $workerPyinstaller packaging/windows/zaya-hand-worker.spec --noconfirm --distpath $workerOutDir
        if ($LASTEXITCODE -ne 0) { throw "ZayaHandWorker.exe build failed." }
    } else {
        Write-Host "`n[2/5] Skipping hand worker build (-SkipWorkerBuild)" -ForegroundColor DarkGray
    }

    # 3. Build main application onedir with PyInstaller
    Write-Host "`n[3/5] Building main Zaya desktop application..." -ForegroundColor Yellow
    if (-not (Test-Path $venvPyinstaller)) {
        Write-Warning "PyInstaller not found in main venv; installing..."
        & $venvPython -m pip install --quiet pyinstaller
    }

    & $venvPyinstaller packaging/windows/zaya.spec --noconfirm --distpath $distWindows
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller packaging for Zaya failed." }

    $appDir = Join-Path $distWindows "Zaya"
    if (-not (Test-Path (Join-Path $appDir "Zaya.exe"))) {
        throw "Build output missing Zaya.exe in $appDir"
    }

    # 4. Integrate hand worker and spatial renderer assets into appDir
    Write-Host "`n[4/5] Integrating worker and auxiliary assets into $appDir..." -ForegroundColor Yellow
    if (Test-Path $workerExe) {
        Copy-Item -Path $workerExe -Destination $appDir -Force
        Write-Host "Copied $workerExe -> $appDir"
    }

    $appRendererDist = Join-Path $appDir "spatial_renderer\dist"
    if ((Test-Path $rendererDist) -and (-not (Test-Path $appRendererDist))) {
        New-Item -ItemType Directory -Path $appRendererDist -Force | Out-Null
        Copy-Item -Path "$rendererDist\*" -Destination $appRendererDist -Recurse -Force
        Write-Host "Synced renderer dist -> $appRendererDist"
    }

    # 5. Build Inno Setup installer and prepare update manifest
    if (-not $SkipInstaller) {
        Write-Host "`n[5/5] Compiling Inno Setup installer and generating update manifest..." -ForegroundColor Yellow
        & $venvPython tools/prepare_windows_release.py --app-dir $appDir --output $distWindows
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation / release prep failed." }
    } else {
        Write-Host "`n[5/5] Skipping installer compilation (-SkipInstaller)" -ForegroundColor DarkGray
    }

    Write-Host "`n=== Build completed successfully! ===" -ForegroundColor Green
    Write-Host "Application folder: $appDir"
    if (Test-Path (Join-Path $distWindows "Zaya-Setup.exe")) {
        Write-Host "Installer: $(Join-Path $distWindows 'Zaya-Setup.exe')" -ForegroundColor Green
    }
    if (Test-Path (Join-Path $distWindows "desktop-update.json")) {
        Write-Host "Manifest: $(Join-Path $distWindows 'desktop-update.json')" -ForegroundColor Green
    }
} finally {
    Pop-Location
}
