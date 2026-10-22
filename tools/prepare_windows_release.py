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

    # Optional code signing of binaries before packaging
    if cert_path and Path(cert_path).is_file():
        signtool = shutil.which("signtool.exe") or shutil.which("signtool")
        if signtool:
            print(f"Signing {zaya_exe.name}...")
            cmd = [signtool, "sign", "/f", str(cert_path), "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256"]
            if cert_password:
                cmd.extend(["/p", cert_password])
            cmd.append(str(zaya_exe))
            subprocess.run(cmd, check=True)

            if worker_exe.is_file():
                print(f"Signing {worker_exe.name}...")
                cmd_w = list(cmd[:-1]) + [str(worker_exe)]
                subprocess.run(cmd_w, check=True)

    # Locate ISCC compiler
    compiler = Path(iscc_path) if iscc_path else find_iscc()
    if not compiler or not compiler.is_file():
        raise RuntimeError("Inno Setup 6 compiler (ISCC.exe) not found. Install Inno Setup 6 to compile Zaya-Setup.exe.")

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

    installer = output_dir / "Zaya-Setup.exe"
    if not installer.is_file():
        raise FileNotFoundError(f"Installer was not created: {installer}")

    # Sign the final installer if certificate provided
    if cert_path and Path(cert_path).is_file():
        signtool = shutil.which("signtool.exe") or shutil.which("signtool")
        if signtool:
            print(f"Signing installer {installer.name}...")
            cmd_inst = [signtool, "sign", "/f", str(cert_path), "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256"]
            if cert_password:
                cmd_inst.extend(["/p", cert_password])
            cmd_inst.append(str(installer))
            subprocess.run(cmd_inst, check=True)

    installer_hash = calculate_sha256(installer)
    installer_size = installer.stat().st_size

    # Write desktop-update.json
    update_manifest = {
        "schema": 1,
        "channel": "stable",
        "version": version,
        "build": int(build),
        "filename": "Zaya-Setup.exe",
        "url": "https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/Zaya-Setup.exe",
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

    print(f"Prepared Windows release: {installer.name} ({installer_size} bytes, sha256: {installer_hash})")
    return update_manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare Windows Zaya-Setup.exe and update manifest.")
    parser.add_argument("--app-dir", required=True, help="Path to dist/windows/Zaya directory")
    parser.add_argument("--output", required=True, help="Path to output distribution directory")
    parser.add_argument("--version", default="0.5.0", help="Release version (e.g. 0.5.0)")
    parser.add_argument("--build", type=int, default=10007, help="Monotonic build number")
    parser.add_argument("--iscc", default=None, help="Path to ISCC.exe compiler")
    parser.add_argument("--cert", default=None, help="Path to Authenticode code-signing PFX")
    parser.add_argument("--cert-password", default=None, help="Password for Authenticode certificate")

    args = parser.parse_args()
    prepare_windows_release(
        app_dir=args.app_dir,
        output_dir=args.output,
        version=args.version,
        build=args.build,
        iscc_path=args.iscc,
        cert_path=args.cert,
        cert_password=args.cert_password,
    )
