# Check, build and publish the APK and Play App Bundle without uploading private source.
$ErrorActionPreference = 'Stop'
$releaseRoot = Split-Path -Parent $PSScriptRoot
$previousCode = $env:ZAYA_VERSION_CODE
$previousName = $env:ZAYA_VERSION_NAME
Push-Location $releaseRoot
try {
    git diff --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Commit tracked changes before publishing.' }
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Commit staged changes before publishing.' }
    if (-not $env:ZAYA_SIGNING_STORE -or -not (Test-Path $env:ZAYA_SIGNING_STORE)) {
        throw 'ZAYA_SIGNING_STORE must point to a valid keystore file path before publishing a release.'
    }
    try {
        $latest = Invoke-RestMethod 'https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/update.json'
        $previous = [long]$latest.version_code
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
        $previous = 0
    }
    $next = [Math]::Max(10001, $previous + 1)
    $env:ZAYA_VERSION_CODE = [string]$next
    $env:ZAYA_VERSION_NAME = '0.4.' + ($next - 10000)
    & .\mobile\android\gradlew.bat -p mobile/android :app:lintRelease --console=plain --max-workers=2
    if ($LASTEXITCODE -ne 0) { throw 'Android lint failed.' }
    & .\mobile\android\gradlew.bat -p mobile/android :app:assembleRelease --console=plain --max-workers=2
    if ($LASTEXITCODE -ne 0) { throw 'Android release build failed.' }
    & .\mobile\android\gradlew.bat -p mobile/android :app:bundleRelease --console=plain --max-workers=2
    if ($LASTEXITCODE -ne 0) { throw 'Android bundle build failed.' }
    $aabPath = "mobile/android/app/build/outputs/bundle/release/app-release.aab"
    $prepareArgs = @(
        "tools/prepare_android_release.py",
        "--apk", "mobile/android/app/build/outputs/apk/release/app-release.apk",
        "--metadata", "mobile/android/app/build/outputs/apk/release/output-metadata.json",
        "--output", "dist/android-release"
    )
    if (Test-Path $aabPath) {
        $prepareArgs += @("--aab", $aabPath)
    }
    & .\.venv\Scripts\python.exe @prepareArgs
    if ($LASTEXITCODE -ne 0) { throw 'Release packaging failed.' }
    gh release create "android-$env:ZAYA_VERSION_NAME" --repo sajancodes/zaya-companion-releases --title "Zaya Companion $env:ZAYA_VERSION_NAME" --notes-file dist/android-release/notes.md --latest dist/android-release/Zaya-Companion.apk dist/android-release/update.json
    if ($LASTEXITCODE -ne 0) { throw 'Public release publishing failed.' }
} finally {
    $env:ZAYA_VERSION_CODE = $previousCode
    $env:ZAYA_VERSION_NAME = $previousName
    Pop-Location
}
