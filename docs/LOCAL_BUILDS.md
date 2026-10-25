# Local builds on the owner's device

Zaya is created and developed by Sajan Rai. GitHub-hosted runners are not required for these builds. The owner starts the pipeline locally; it does not register a persistent remote runner.

From the repository root in PowerShell:

```powershell
.\tools\local_windows_pipeline.ps1 -Stage Preflight
.\tools\local_windows_pipeline.ps1 -Stage Prepare
.\tools\local_windows_pipeline.ps1 -Stage Build
```

`Prepare` uses Python 3.11 to create `.venv-local-release` and `.venv-local-hands`, both ignored by Git. Existing `.venv`, `.venv-hands`, running Zaya processes and credentials are preserved. Rerun Prepare when requirement files change. Use `-BuildPython <absolute-path>` if Python 3.11 is installed elsewhere.

`Build` requires tracked changes to be committed. It exports HEAD to a fresh ignored directory, then verifies and builds that exact snapshot. Ignored/untracked owner settings, conversation databases and linked WhatsApp sessions are not exported. Tests use a separate temporary user-data directory. Gates include fatal lint, repository tests, dependency audits, both frontend builds/audits and packaging of the main executable and hand worker. Missing worker/renderer output is an error.

Output is under `dist/local-builds/<commit>-<attempt>/windows/Zaya/`. This is an **unsigned application folder for local testing**, not a signed setup file or a verified public release. `build-receipt.json` records the source commit and status; dependency-version lists are stored alongside it. No command here automatically publishes artifacts.

## Trusted Windows installer

Before `-Stage Release`, install Inno Setup 6 and the Windows SDK signing tools, and configure an appropriate trusted code-signing identity. The current signer integration takes an authorized PFX path in `ZAYA_SIGNING_CERT_PATH` and its password through `ZAYA_SIGNING_CERT_PASSWORD`; do not put passwords in commands, source or Git. A hardware/cloud-backed signing provider may require a separate signing integration rather than an exportable PFX.

```powershell
.\tools\local_windows_pipeline.ps1 -Stage Release
```

This refuses to run without signing prerequisites. The application, worker and installer must pass signing/verification before update metadata is produced. Release also requires active Windows Defender and a completed custom scan without newly detected threats. A self-signed certificate is not a substitute for publicly trusted signing. Trusted signing does not guarantee SmartScreen reputation or remove the need for clean installation, upgrade and uninstall tests. Until those checks pass, the receipt deliberately does not mark the artifact as a verified public release. Use a currently patched Python 3.11 installation for public builds; the script checks the minor version, not interpreter security support.

## Linux on this device

Linux PyInstaller builds must run inside Linux. On this Windows laptop that requires a Linux VM or WSL2/Ubuntu; enabling/installing that environment may require administrator action and a restart. It is not installed automatically by this script. Follow `packaging/linux/README.md` inside a native Ubuntu 22.04 amd64 test environment. Preserve the Windows and Linux output channels separately.
