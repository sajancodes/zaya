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


## Fedora RPM and portable archive

`python tools/prepare_linux_variants.py --app-dir dist/linux-app-public/Zaya --output dist/linux-variants` creates `Zaya.rpm` and `Zaya-linux-x86_64.tar.gz` from the same clean native payload. The build environment also needs `rpm`/`rpmbuild`. The existing payload privacy checks run before either format is created; existing artifacts are never overwritten. RPM post-processing does not strip or expose the embedded application libraries as system-library providers. Archive ownership is normalized, and RPM build-host metadata uses a generic label.

The RPM declares glibc 2.35 or newer and its external runtime dependencies. Fedora 44 container verification passed dependency resolution, installation, a normal-user X11 startup outside a source checkout, package integrity checks and uninstall preserving `~/.zaya`. This is a headless smoke check, not physical microphone/camera or desktop-automation certification. Fedora dependency references: [ALSA PulseAudio adapter](https://packages.fedoraproject.org/pkgs/alsa-plugins/alsa-plugins-pulseaudio/index.html) and [FFmpeg](https://packages.fedoraproject.org/pkgs/ffmpeg/ffmpeg-free/).

Portable extraction and normal-user startup passed on Ubuntu 22.04; extracted executables matched the original payload, and startup did not modify the application folder. Other modern glibc-based x86-64 distributions can use the archive after installing the libraries listed in its included README. They are not individually certified. Older RHEL/Rocky/Alma versions below glibc 2.35 and musl-based systems are not supported by these binaries. Wayland desktop automation remains limited. Atomic/immutable Fedora editions need their own installation approach; the documented `dnf` command targets conventional Fedora desktops.
