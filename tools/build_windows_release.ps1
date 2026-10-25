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
    [switch]$SkipInstaller,
    [string]$PythonPath,
    [string]$WorkerPythonPath,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    Write-Host "=== Zaya Windows Desktop Distribution Build ===" -ForegroundColor Cyan
    Write-Host "Repository root: $repoRoot"

    $venvPython = if ($PythonPath) { $PythonPath } else { Join-Path $repoRoot '.venv\Scripts\python.exe' }
    $handsPython = if ($WorkerPythonPath) { $WorkerPythonPath } else { Join-Path $repoRoot '.venv-hands\Scripts\python.exe' }

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
                        Write-Host "Restoring renderer dependencies from its lockfile..."
                        & npm ci --no-audit --no-fund
                        if ($LASTEXITCODE -ne 0) { throw 'Renderer dependency restore failed.' }
                    }
                    Write-Host "Running npm run build..."
                    & npm run build
                    if ($LASTEXITCODE -ne 0) { throw "Renderer npm build failed." }
                } finally {
                    Pop-Location
                }
            } else {
                throw 'npm is required to build the renderer.'
            }
        }
    } else {
        Write-Host "`n[1/5] Skipping spatial renderer build (-SkipRendererBuild)" -ForegroundColor DarkGray
    }

    # Verify renderer dist exists
    if (-not (Test-Path (Join-Path $rendererDist "index.html"))) {
        throw 'spatial_renderer/dist/index.html is required; no placeholder renderer will be packaged.'
    }

    # 2. Build isolated hand tracking worker executable (ZayaHandWorker.exe)
    $distWindows = if ($OutputDirectory) { $OutputDirectory } else { Join-Path $repoRoot 'dist\windows' }
    $workerOutDir = Join-Path $distWindows "worker"
    $workerExe = Join-Path $workerOutDir "ZayaHandWorker.exe"

    if (-not $SkipWorkerBuild) {
        Write-Host "`n[2/5] Building isolated hand tracking worker (ZayaHandWorker.exe)..." -ForegroundColor Yellow
        $workerPython = if (Test-Path $handsPython) { $handsPython } else { $venvPython }
        & $workerPython -m PyInstaller packaging/windows/zaya-hand-worker.spec --noconfirm --distpath $workerOutDir
        if ($LASTEXITCODE -ne 0) { throw "ZayaHandWorker.exe build failed." }
    } else {
        Write-Host "`n[2/5] Skipping hand worker build (-SkipWorkerBuild)" -ForegroundColor DarkGray
    }

    # 3. Build main application onedir with PyInstaller
    Write-Host "`n[3/5] Building main Zaya desktop application..." -ForegroundColor Yellow
    & $venvPython -m PyInstaller packaging/windows/zaya.spec --noconfirm --distpath $distWindows
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
    } else {
        throw 'The isolated hand worker is required for a complete desktop build.'
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
