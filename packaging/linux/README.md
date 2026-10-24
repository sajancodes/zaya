# Native Linux candidate

Created and developed by Sajan Rai. This build path produces a **private candidate**, not a verified public Linux release.

Run the `Native Linux candidate (private verification)` GitHub workflow when hosted Actions is available, or use an Ubuntu 22.04 amd64 machine/WSL2 environment with its listed dependencies. PyInstaller must run on Linux. The workflow builds the spatial renderer, application and isolated hand worker, then assembles `Zaya.deb` with desktop integration and native dependencies. It never publishes to the public release repository.

The shared packaging specs retain the same explicit data allowlist as Windows. Assembly rejects Windows PE binaries, private runtime databases/configuration/signing files and symlinks escaping the payload. Version/build come from `version.json`; the candidate records a real SHA-256 and size with `public_release_verified: false`. No source environment or owner configuration is copied into the package.

Before promotion, verify on a clean Linux test system:

1. Install with `sudo apt install ./Zaya.deb`; launch `zaya` from a normal desktop session without Python or a source checkout. Verify all bundled resources and renderer startup.
2. Verify first-run onboarding, microphone/audio, provider connectivity and an unlocked Secret Service keyring. Missing/locked secure storage must reject credential writes rather than store base64.
3. Verify camera permissions, the native hand worker and graceful child cleanup. X11 desktop automation and Wayland restrictions must be reported accurately; Windows-only controls must never be claimed as Linux capabilities.
4. Upgrade using a later candidate with `sudo apt install ./Zaya.deb`; preserve `~/.zaya`, settings, archives, credentials, phone pairing and projects.
5. Remove with `sudo apt remove zaya`; confirm application files are removed while user data remains. Package scripts never delete user data.
6. Establish a reviewed Linux artifact-signing/provenance and update channel before public promotion. The Windows `.exe` updater is guarded on Linux; updates use the native package manager. No Linux automatic-update service is claimed.

Local build verified on 24 October 2026: Ubuntu 22.04.5 AMD64 under WSL2, Python 3.11.17 and Node 20.20.2. Eight focused checks, dependency audit, encrypted Secret Service roundtrip, native worker model loading, and normal-user installation/startup/removal checks passed. Audio devices and the required formats are available in WSL; physical Linux microphone/camera and full desktop automation were not verified. Reinstallation preserved user data; upgrade from a different canonical version remains unverified.

The manually published [experimental unsigned Linux beta](https://github.com/sajancodes/zaya-companion-releases/releases/tag/linux-0.5.0-beta.1) is distinct from stable promotion. It includes the installer, checksum and build metadata only. The candidate manifest deliberately retains `public_release_verified: false`. Linux updates remain manual; no signing or automatic-update service is claimed. The website advertises the beta explicitly through its checked-in public release metadata, matching the Windows beta approach.
