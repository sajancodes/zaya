# Unsigned Windows beta

Owner-authorized manual distribution, created by Sajan Rai. This is not the signed stable release path.

Build the isolated app with `tools/local_windows_pipeline.ps1 -Stage Build`, then run:

```powershell
.venv-local-release\Scripts\python.exe tools/prepare_windows_release.py --app-dir <clean-app-folder> --output <fresh-output-folder> --channel beta --unsigned-beta --tag windows-0.5.0-beta.1
```

The explicit flag produces ZayaBetaSetup.exe, windows-beta.json and SHA256SUMS.txt. It rejects stable-channel use and private runtime files. It never creates desktop-update.json or changes Authenticode verification in the installed updater. The beta is manually downloaded and installed; merely uploading a new beta does not update existing installations.

The first candidate derives from the verified e9d32b9 application/worker build. Its clean staging folder excludes runtime logs and the incompatible build-host ICU DLL, and adds the tracked default zayabar.json and sad.png resource. The committed PyInstaller spec includes those corrections for future builds. The first-run Settings screen and taskbar companion were observed on the owner's Windows device; the owner confirmed the character appeared. No provider credentials were entered in that test profile. This is not clean-machine certification, nor proof of every voice, phone, wake/restart or automation feature.

Before uploading, scan the completed installer, exercise installation into a separate test directory, verify installed resources and preserve all owner data. Upload only the installer, beta integrity metadata and release notes to the public APK/artifact repository. Keep source private. The website's pinned beta download is enabled only after the actual GitHub asset digest and size match local metadata.

Invite a small early-testing group. Expect Windows reputation warnings or outright blocks on some devices. Never instruct users to disable antivirus or Smart App Control. Publish screenshots from the real installer and fresh first-run profile; do not represent illustrations as captured Windows warnings.
