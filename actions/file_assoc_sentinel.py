"""Windows Default Applications & File Associations Sentinel.
Created and developed by Sajan Rai for Zaya.

Queries and audits Windows default application associations across file extensions
(documents, media, web, code, archives) using pure Win32 shlwapi APIs.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.execution_policy import require_owner


ASSOCF_NONE = 0
ASSOCSTR_COMMAND = 1
ASSOCSTR_EXECUTABLE = 2
ASSOCSTR_FRIENDLYAPPNAME = 4

_COMMON_EXTENSIONS = [
    (".pdf", "Documents"),
    (".docx", "Documents"),
    (".txt", "Documents"),
    (".csv", "Documents"),
    (".html", "Web & Browsers"),
    (".svg", "Web & Browsers"),
    (".mp4", "Media"),
    (".mp3", "Media"),
    (".jpg", "Media"),
    (".png", "Media"),
    (".py", "Code & Development"),
    (".js", "Code & Development"),
    (".json", "Code & Development"),
    (".zip", "Archives"),
    (".rar", "Archives"),
    (".7z", "Archives"),
]


def _query_assoc_string(ext: str, str_type: int) -> Optional[str]:
    """Query an association string via Win32 AssocQueryStringW."""
    if os.name != "nt":
        return None

    try:
        shlwapi = ctypes.windll.shlwapi
        buf_size = wintypes.DWORD(1024)
        buf = (wintypes.WCHAR * 1024)()
        hr = shlwapi.AssocQueryStringW(
            ASSOCF_NONE,
            str_type,
            ext,
            None,
            buf,
            ctypes.byref(buf_size),
        )
        if hr == 0 and buf.value:
            return buf.value.strip()
    except Exception:
        pass
    return None


def get_default_app_for_extension(ext: str) -> Dict[str, Any]:
    """Retrieve the registered default application and executable for a file extension."""
    clean_ext = ext.strip().lower()
    if not clean_ext.startswith("."):
        clean_ext = f".{clean_ext}"

    friendly = _query_assoc_string(clean_ext, ASSOCSTR_FRIENDLYAPPNAME)
    exe_path = _query_assoc_string(clean_ext, ASSOCSTR_EXECUTABLE)

    # Fallback to exe name if friendly name is missing
    if not friendly and exe_path:
        friendly = Path(exe_path).stem.capitalize()

    is_associated = bool(friendly or exe_path)

    return {
        "status": "associated" if is_associated else "not_associated",
        "extension": clean_ext,
        "friendly_name": friendly or "Unknown / Not Associated",
        "executable_path": exe_path or "None",
        "is_associated": is_associated,
    }


def get_common_associations_audit() -> Dict[str, Any]:
    """Audit default application associations across standard file categories."""
    categorized: Dict[str, List[Dict[str, Any]]] = {}

    for ext, cat in _COMMON_EXTENSIONS:
        info = get_default_app_for_extension(ext)
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append({
            "extension": ext,
            "app": info["friendly_name"],
            "executable": info["executable_path"],
            "is_associated": info["is_associated"],
        })

    # High level highlights
    pdf_app = get_default_app_for_extension(".pdf")["friendly_name"]
    web_app = get_default_app_for_extension(".html")["friendly_name"]
    zip_app = get_default_app_for_extension(".zip")["friendly_name"]
    txt_app = get_default_app_for_extension(".txt")["friendly_name"]

    return {
        "status": "success",
        "highlights": {
            "browser_default": web_app,
            "pdf_reader": pdf_app,
            "archive_manager": zip_app,
            "text_editor": txt_app,
        },
        "categories": categorized,
    }


def file_assoc_sentinel(parameters: Optional[Dict[str, Any]] = None, **_kwargs) -> str:
    """Action entry point for inspecting default file associations and handlers."""
    require_owner()
    params = parameters or {}
    action = str(params.get("action") or "summary").lower().strip()

    if action in ("summary", "audit", "status"):
        audit = get_common_associations_audit()
        hl = audit["highlights"]
        summary = (
            f"Default Applications: Web Browser: {hl['browser_default']} (.html), "
            f"PDF: {hl['pdf_reader']}, Archives: {hl['archive_manager']} (.zip), "
            f"Editor: {hl['text_editor']} (.txt)."
        )
        return json.dumps({
            "status": "success",
            "summary": summary,
            "data": audit,
        }, indent=2)

    if action in ("lookup", "check", "get"):
        ext = params.get("extension") or params.get("ext")
        if not ext:
            return json.dumps({
                "status": "error",
                "message": "Must provide 'extension' to lookup (e.g. '.pdf', 'mp4', '.zip')."
            }, indent=2)

        info = get_default_app_for_extension(str(ext))
        exe_txt = f" ({info['executable_path']})" if info['executable_path'] != "None" else ""
        summary = f"Default app for {info['extension']}: {info['friendly_name']}{exe_txt}."
        return json.dumps({
            "status": "success" if info["is_associated"] else "not_associated",
            "summary": summary,
            "data": info,
        }, indent=2)

    return json.dumps({
        "status": "error",
        "message": f"Unknown action '{action}'. Choose from: summary, lookup.",
    }, indent=2)


TOOL = {
    "name": "file_assoc_sentinel",
    "description": "Inspect Windows default application associations by file extension (e.g. .pdf, .mp4, .zip, .html, .py). Check friendly application names and executable paths.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["summary", "lookup"],
                "description": "File association action (default: 'summary').",
            },
            "extension": {
                "type": "STRING",
                "description": "File extension to check (e.g. 'pdf', '.mp4', '.zip') when action is 'lookup'.",
            },
        },
    },
    "handler": file_assoc_sentinel,
}
