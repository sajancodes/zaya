"""Prepare Windows release installer, manifest, and checksums.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _run_signing(command):
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        # CalledProcessError includes argv, which can contain the PFX password.
        raise RuntimeError(f'Code signing failed (exit {error.returncode}); signing credentials withheld.') from None


def calculate_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest().lower()


def find_iscc() -> Path | None:
    """Locate Inno Setup compiler ISCC.exe."""
    cmd_iscc = shutil.which("iscc.exe") or shutil.which("ISCC.exe")
    if cmd_iscc:
        return Path(cmd_iscc)

    common_paths = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    ]
    for p in common_paths:
        if p.is_file():
            return p
    return None


def prepare_windows_release(
    app_dir: str | Path,
    output_dir: str | Path,
    version: str,
    build: int,
    channel: str = "stable",
    tag: str | None = None,
    iscc_path: str | Path | None = None,
    cert_path: str | Path | None = None,
    cert_password: str | None = None,
) -> dict:
    app_dir = Path(app_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    zaya_exe = app_dir / "Zaya.exe"
    if not zaya_exe.is_file():
        raise FileNotFoundError(f"Missing packaged executable: {zaya_exe}")

    worker_exe = app_dir / "ZayaHandWorker.exe"
    if not worker_exe.is_file():
        print(f"[Warning] ZayaHandWorker.exe not found in {app_dir}; hand features will rely on runtime fallback.")

    # Public releases fail closed; unsigned builds are local previews only.
    if not cert_path or not Path(cert_path).is_file():
        raise RuntimeError('A production Authenticode certificate is required; no unsigned installer will be published.')
    if not (shutil.which('signtool.exe') or shutil.which('signtool')):
        raise RuntimeError('Windows SDK signtool is required for signing and verification.')
    # Sign binaries before packaging.
    if cert_path and Path(cert_path).is_file():
        signtool = shutil.which("signtool.exe") or shutil.which("signtool")
        if signtool:
            print(f"Signing {zaya_exe.name}...")
            cmd = [signtool, "sign", "/f", str(cert_path), "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256"]
            if cert_password:
                cmd.extend(["/p", cert_password])
            cmd.append(str(zaya_exe))
            _run_signing(cmd)
            subprocess.run([signtool, 'verify', '/pa', '/all', str(zaya_exe)], check=True)

            if worker_exe.is_file():
                print(f"Signing {worker_exe.name}...")
                cmd_w = list(cmd[:-1]) + [str(worker_exe)]
                _run_signing(cmd_w)
                subprocess.run([signtool, 'verify', '/pa', '/all', str(worker_exe)], check=True)

    # Locate ISCC compiler
    compiler = Path(iscc_path) if iscc_path else find_iscc()
    if not compiler or not compiler.is_file():
        raise RuntimeError("Inno Setup 6 compiler (ISCC.exe) not found. Install Inno Setup 6 to compile ZayaSetup.exe.")

    iss_script = Path(__file__).resolve().parents[1] / "packaging" / "windows" / "Zaya.iss"
    if not iss_script.is_file():
        raise FileNotFoundError(f"Missing Inno Setup script: {iss_script}")

    print(f"Building Windows installer via {compiler}...")
    iscc_cmd = [
        str(compiler),
        f"/DMyAppVersion={version}",
        f"/DMyAppBuild={build}",
        f"/DSourceAppDir={app_dir}",
        f"/O{output_dir}",
        str(iss_script)
    ]
    subprocess.run(iscc_cmd, check=True)

    installer = output_dir / "ZayaSetup.exe"
    if not installer.is_file():
        installer_alt = output_dir / "Zaya-Setup.exe"
        if installer_alt.is_file():
            shutil.copyfile(installer_alt, installer)

    if not installer.is_file():
        raise FileNotFoundError(f"Installer was not created: {installer}")

    # 1. Sign the primary installer first if certificate provided
    if cert_path and Path(cert_path).is_file():
        signtool = shutil.which("signtool.exe") or shutil.which("signtool")
        if signtool:
            print(f"Signing canonical installer {installer.name}...")
            cmd_inst = [signtool, "sign", "/f", str(cert_path), "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256"]
            if cert_password:
                cmd_inst.extend(["/p", cert_password])
            cmd_inst.append(str(installer))
            _run_signing(cmd_inst)
            subprocess.run([signtool, 'verify', '/pa', '/all', str(installer)], check=True)

    # 2. Mirror the signed installer to the backward-compatible alias Zaya-Setup.exe
    shutil.copyfile(installer, output_dir / "Zaya-Setup.exe")

    installer_hash = calculate_sha256(installer)
    installer_size = installer.stat().st_size

    # URL resolution: beta releases are prereleases (not latest), requiring tag-specific URL
    release_tag = tag or f"v{version}"
    download_url = f"https://github.com/sajancodes/zaya-companion-releases/releases/download/{release_tag}/ZayaSetup.exe"

    # Write desktop-update.json pointing to canonical installer
    update_manifest = {
        "schema": 1,
        "channel": channel,
        "version": version,
        "build": int(build),
        "filename": "ZayaSetup.exe",
        "url": download_url,
        "sha256": installer_hash,
        "size": installer_size,
    }
    manifest_path = output_dir / "desktop-update.json"
    manifest_path.write_text(json.dumps(update_manifest, indent=2) + "\n", encoding="utf-8")

    # Copy setup.txt
    repo_root = Path(__file__).resolve().parents[1]
    setup_txt = repo_root / "setup.txt"
    if setup_txt.is_file():
        shutil.copy2(setup_txt, output_dir / "setup.txt")

    print(f"Windows release prepared: {installer.name} ({installer_size} bytes, SHA-256: {installer_hash}, channel: {channel})")
    return update_manifest


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.version import VERSION, BUILD, CHANNEL

    parser = argparse.ArgumentParser(description="Build Inno Setup installer and update metadata.")
    parser.add_argument("--app-dir", required=True, help="Path to PyInstaller Zaya onedir output.")
    parser.add_argument("--output", required=True, help="Destination directory for installer and manifest.")
    parser.add_argument("--version", default=VERSION, help="Semantic version string.")
    parser.add_argument("--build", type=int, default=BUILD, help="Integer build code.")
    parser.add_argument("--channel", default=CHANNEL, choices=["stable", "beta"], help="Release channel from canonical version.json.")
    parser.add_argument("--tag", default=None, help="Explicit release tag (e.g. v0.5.1).")
    parser.add_argument("--iscc", default=None, help="Explicit path to ISCC.exe.")
    parser.add_argument("--cert", default=os.environ.get('ZAYA_SIGNING_CERT_PATH'), help="Production PFX certificate path.")
    parser.add_argument("--cert-password", default=os.environ.get('ZAYA_SIGNING_CERT_PASSWORD'), help="Prefer the signing password environment variable.")
    args = parser.parse_args()

    prepare_windows_release(
        app_dir=args.app_dir,
        output_dir=args.output,
        version=args.version,
        build=args.build,
        channel=args.channel,
        tag=args.tag,
        iscc_path=args.iscc,
        cert_path=args.cert,
        cert_password=args.cert_password,
    )
