<# Local, owner-started release pipeline. No persistent remote runner is installed. #>
[CmdletBinding()]
param(
    [ValidateSet('Preflight','Prepare','Verify','Build','Release')]
    [string]$Stage = 'Preflight',
    [string]$BuildPython = (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe')
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$mainPython = Join-Path $projectRoot '.venv-local-release\Scripts\python.exe'
$workerPython = Join-Path $projectRoot '.venv-local-hands\Scripts\python.exe'

function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Local pipeline step failed (exit $LASTEXITCODE)." }
}

function Get-InputHash {
    return ((Get-FileHash (Join-Path $projectRoot 'requirements.txt')).Hash +
            (Get-FileHash (Join-Path $projectRoot 'requirements-hands.txt')).Hash +
            (Get-FileHash (Join-Path $projectRoot 'web\requirements.txt')).Hash)
}

Push-Location $projectRoot
try {
    $signTool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if (-not $signTool) {
        $sdkRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
        if (Test-Path $sdkRoot) {
            $candidate = Get-ChildItem -LiteralPath $sdkRoot -Filter signtool.exe -Recurse |
                Where-Object { $_.Directory.Name -eq 'x64' } | Sort-Object FullName -Descending | Select-Object -First 1
            if ($candidate) { $env:PATH = $candidate.DirectoryName + ';' + $env:PATH; $signTool = $candidate }
        }
    }
    $inno = @((Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
              (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
              (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')) |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    $certificatePresent = [bool]($env:ZAYA_SIGNING_CERT_PATH -and (Test-Path -LiteralPath $env:ZAYA_SIGNING_CERT_PATH))
    if ($Stage -eq 'Preflight') {
        [pscustomobject]@{ Python311=(Test-Path $BuildPython); Node=[bool](Get-Command node -ErrorAction SilentlyContinue);
            MainBuildEnvironment=(Test-Path $mainPython); WorkerBuildEnvironment=(Test-Path $workerPython);
            InnoSetup=[bool]$inno; SignTool=[bool]$signTool; SigningCertificate=$certificatePresent }
        return
    }
    if ($Stage -eq 'Prepare') {
        if (-not (Test-Path $BuildPython)) { throw 'Install Python 3.11 or specify -BuildPython with its absolute path.' }
        Invoke-Checked $BuildPython @('-c', 'import sys; assert sys.version_info[:2] == (3,11), "Use Python 3.11 for release builds"')
        foreach ($environment in @('.venv-local-release', '.venv-local-hands')) {
            $environmentPath = Join-Path $projectRoot $environment
            if (-not (Test-Path $environmentPath)) { Invoke-Checked $BuildPython @('-m','venv',$environmentPath) }
            Invoke-Checked (Join-Path $environmentPath 'Scripts\python.exe') @('-m','pip','install','--upgrade','pip','setuptools','wheel','--quiet')
        }
        Invoke-Checked $mainPython @('-m','pip','install','--quiet','-r','requirements.txt','-r','web/requirements.txt','pyinstaller','ruff','pytest','httpx','pip-audit')
        Invoke-Checked $workerPython @('-m','pip','install','--quiet','-r','requirements-hands.txt','pyinstaller','pip-audit')
        Get-InputHash | Set-Content (Join-Path $projectRoot '.venv-local-release\prepared-inputs.sha256')
        Write-Host 'Dedicated local build environments prepared. Existing Zaya environments were not changed.'
        return
    }
    $stamp = Join-Path $projectRoot '.venv-local-release\prepared-inputs.sha256'
    if (-not (Test-Path $mainPython) -or -not (Test-Path $workerPython) -or -not (Test-Path $stamp)) {
        throw 'Run -Stage Prepare first.'
    }
    if ((Get-Content $stamp -Raw).Trim() -ne (Get-InputHash)) { throw 'Requirements changed. Run -Stage Prepare again.' }
    if ($Stage -eq 'Release' -and (-not $certificatePresent -or -not $signTool -or -not $inno)) {
        throw 'Public installer build requires a trusted signing certificate, Windows SDK SignTool and Inno Setup. Run -Stage Build for a local unsigned application folder.'
    }
    if ($Stage -in @('Build','Release')) {
        $trackedChanges = & git status --porcelain --untracked-files=no
        if ($LASTEXITCODE -ne 0 -or $trackedChanges) { throw 'Commit tracked changes before packaging an identifiable source snapshot.' }
    }
    $source = $projectRoot
    if ($Stage -in @('Build','Release')) {
        $revision = (& git rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $revision -notmatch '^[a-f0-9]{40}$') { throw 'Cannot determine source revision.' }
        $attempt = Join-Path $projectRoot ('dist\local-builds\' + $revision.Substring(0,12) + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
        New-Item -ItemType Directory -Path $attempt | Out-Null
        $archive = Join-Path $attempt 'source.zip'
        Invoke-Checked 'git' @('archive','--format=zip',"--output=$archive",'HEAD')
        $source = Join-Path $attempt 'source'
        Expand-Archive -LiteralPath $archive -DestinationPath $source
    }
    Push-Location $source
    try {
    $priorQt = $env:QT_QPA_PLATFORM
    $priorUserData = $env:ZAYA_USER_DATA_DIR
    try {
        $env:QT_QPA_PLATFORM = 'offscreen'
        $env:ZAYA_USER_DATA_DIR = Join-Path $projectRoot ('dist\local-verification\Zaya-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $env:ZAYA_USER_DATA_DIR | Out-Null
        Invoke-Checked $mainPython @('-m','ruff','check','--isolated','--select','E9,F63,F7,F82','core','actions','services','memory','main.py','ui.py','dashboard','plugins','tools','web')
        Invoke-Checked $mainPython @('-m','pytest','tests','-q','--disable-warnings')
        Invoke-Checked $mainPython @('-m','pip','check')
        Invoke-Checked $workerPython @('-m','pip','check')
        # Audit the exact installed packages being frozen, including transitive dependencies.
        Invoke-Checked $mainPython @('-m','pip_audit','--progress-spinner','off','--timeout','30')
        Invoke-Checked $workerPython @('-m','pip_audit','--progress-spinner','off','--timeout','30')
    } finally { $env:QT_QPA_PLATFORM = $priorQt; $env:ZAYA_USER_DATA_DIR = $priorUserData }
    if ($Stage -eq 'Verify') { Write-Host 'Local Python verification gates passed.'; return }
    foreach ($frontend in @('web','spatial_renderer')) {
        Push-Location (Join-Path $source $frontend)
        try {
            Invoke-Checked 'npm.cmd' @('ci','--no-fund')
            Invoke-Checked 'npm.cmd' @('audit','--audit-level=high')
            Invoke-Checked 'npm.cmd' @('run','build')
        } finally { Pop-Location }
    }
    $output = Join-Path $attempt 'windows'
    & (Join-Path $source 'tools\build_windows_release.ps1') -PythonPath $mainPython -WorkerPythonPath $workerPython -OutputDirectory $output -SkipRendererBuild -SkipInstaller:($Stage -ne 'Release')
    if ($LASTEXITCODE -ne 0) { throw 'Native build failed.' }
    if ($Stage -eq 'Release') {
        $scanStarted = Get-Date
        $defender = Get-MpComputerStatus -ErrorAction Stop
        if (-not $defender.AntivirusEnabled -or -not $defender.RealTimeProtectionEnabled) {
            throw 'Windows Defender must be active before a public release can pass.'
        }
        Start-MpScan -ScanType CustomScan -ScanPath $output -ErrorAction Stop
        if (Get-MpThreatDetection -ErrorAction Stop | Where-Object { $_.InitialDetectionTime -ge $scanStarted }) {
            throw 'Defender reported a threat during release verification; publication is blocked.'
        }
    }
    $mainPackages = & $mainPython -m pip freeze
    if ($LASTEXITCODE -ne 0) { throw 'Could not record application dependency versions.' }
    [IO.File]::WriteAllLines((Join-Path $attempt 'python-packages.txt'), [string[]]$mainPackages)
    $workerPackages = & $workerPython -m pip freeze
    if ($LASTEXITCODE -ne 0) { throw 'Could not record worker dependency versions.' }
    [IO.File]::WriteAllLines((Join-Path $attempt 'worker-packages.txt'), [string[]]$workerPackages)
    $files = @('Zaya\Zaya.exe','Zaya\ZayaHandWorker.exe','ZayaSetup.exe') | ForEach-Object {
        $artifactPath = Join-Path $output $_
        if (Test-Path $artifactPath) { @{filename=$_; size=(Get-Item $artifactPath).Length; sha256=(Get-FileHash $artifactPath).Hash.ToLowerInvariant()} }
    }
    $version = Get-Content (Join-Path $source 'version.json') -Raw | ConvertFrom-Json
    $receipt = @{ source_commit=$revision; version=$version.version; build=$version.build; stage=$Stage; built_at_utc=[datetime]::UtcNow.ToString('o');
       files=@($files); output=$output; public_release_verified=$false; note='Clean install, upgrade and uninstall verification remains required. No automatic publishing.' }
    [IO.File]::WriteAllText((Join-Path $attempt 'build-receipt.json'), ($receipt | ConvertTo-Json -Depth 5))
    Write-Host "Local build complete: $output"
    Write-Host 'This command does not publish artifacts or claim clean-machine installation verification.'
    } finally { Pop-Location }
} finally { Pop-Location }
