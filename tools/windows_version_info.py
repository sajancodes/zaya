"""Canonical Windows PE metadata for Zaya binaries, created by Sajan Rai."""
from __future__ import annotations

import json
from pathlib import Path
import re


def version_fields(root: Path, executable: str) -> tuple[tuple[int, ...], dict[str, str]]:
    """Keep Explorer version information aligned with the updater manifest."""
    data = json.loads((root / "version.json").read_text(encoding="utf-8"))
    version = data["version"]
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.-]+)?", version)
    if not match or executable not in {"Zaya.exe", "ZayaHandWorker.exe"}:
        raise ValueError("Invalid Windows version metadata")
    build = data["build"]
    if isinstance(build, bool) or not isinstance(build, int):
        raise ValueError("Windows build must be an integer")
    numbers = (*map(int, match.groups()), build)
    if any(number < 0 or number > 65535 for number in numbers):
        raise ValueError("Windows version components must fit unsigned 16-bit fields")
    return numbers, {
        "CompanyName": "Sajan Rai",
        "FileDescription": "Zaya AI Assistant" if executable == "Zaya.exe" else "Zaya Hand Tracking Worker",
        "FileVersion": ".".join(map(str, numbers)),
        "InternalName": executable.removesuffix(".exe"),
        "OriginalFilename": executable,
        "ProductName": "Zaya",
        "ProductVersion": version,
        "LegalCopyright": "Copyright Sajan Rai. See LICENSE and CREDITS for upstream attribution.",
    }


def build_version_info(root: Path, executable: str):
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable,
        VarFileInfo, VarStruct, VSVersionInfo,
    )
    numbers, fields = version_fields(root, executable)
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3F,
                          flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
        kids=[StringFileInfo([StringTable("040904B0", [StringStruct(k, v) for k, v in fields.items()])]),
              VarFileInfo([VarStruct("Translation", [1033, 1200])])],
    )
