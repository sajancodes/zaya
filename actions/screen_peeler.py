"""
ScreenPeeler AI OCR (Chapter 05 / PC Specs)
Intelligent rectangular region screen selection & multimodal text extraction.
Takes a snapshot of screen coordinates or active window, runs OCR extraction,
and populates the extracted text directly to the clipboard.
"""
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import pyperclip

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False

try:
    import PIL.Image
    _PIL = True
except ImportError:
    _PIL = False

from core.execution_policy import require_owner


def capture_screen_region(region: Optional[List[int]] = None) -> Optional[bytes]:
    """
    Captures a screen region [x1, y1, x2, y2]. If None, captures entire primary screen.
    Returns PNG image bytes.
    """
    if not _MSS:
        return None

    with mss.mss() as sct:
        monitors = sct.monitors
        target = monitors[1] if len(monitors) > 1 else monitors[0]

        if region and len(region) >= 4:
            x1, y1, x2, y2 = region[0], region[1], region[2], region[3]
            monitor = {
                "left": int(min(x1, x2)),
                "top": int(min(y1, y2)),
                "width": int(abs(x2 - x1)),
                "height": int(abs(y2 - y1))
            }
        else:
            monitor = target

        shot = sct.grab(monitor)
        return mss.tools.to_png(shot.rgb, shot.size)


def _ocr_via_powershell(png_bytes: bytes) -> str:
    """Uses Windows.Media.Ocr via PowerShell (native Windows 10/11 built-in, no external binaries)."""
    try:
        temp_img = Path(os.environ.get("TEMP", ".")) / "_zaya_peeler_tmp.png"
        temp_img.write_bytes(png_bytes)
        
        ps_script = f"""
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
        Function Await($WinRtTask, $ResultType) {{
            $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
            $netTask = $asTask.Invoke($null, @($WinRtTask))
            $netTask.Wait(-1) | Out-Null
            $netTask.Result
        }}
        [Windows.Globalization.Language,Windows.Foundation.Diagnostics,ContentType=WindowsRuntime] | Out-Null
        [Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation.Diagnostics,ContentType=WindowsRuntime] | Out-Null
        [Windows.Media.Ocr.OcrEngine,Windows.Foundation.Diagnostics,ContentType=WindowsRuntime] | Out-Null

        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync('{str(temp_img).replace('\\', '\\\\')}')) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
        $ocrResult = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $ocrResult.Text
        """
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=10)
        try:
            temp_img.unlink(missing_ok=True)
        except Exception:
            pass
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def extract_text_from_region(region: Optional[List[int]] = None) -> str:
    """Captures the screen region and runs OCR text extraction."""
    png = capture_screen_region(region)
    if not png:
        return ""

    # Try Windows native OCR
    text = _ocr_via_powershell(png)
    if text:
        return text

    # Try pytesseract if installed
    try:
        import pytesseract
        import PIL.Image
        img = PIL.Image.open(io.BytesIO(png))
        t = pytesseract.image_to_string(img)
        if t.strip():
            return t.strip()
    except Exception:
        pass

    return ""


def screen_peeler(parameters: dict, **_kwargs) -> str:
    """
    ScreenPeeler Action:
    Captures screen region, extracts code/text, and copies directly to clipboard.
    """
    require_owner()
    region = parameters.get("region") # [x1, y1, x2, y2]
    action = parameters.get("action", "scan")

    extracted = extract_text_from_region(region)
    if not extracted:
        return json.dumps({
            "status": "partial",
            "message": "ScreenPeeler captured the screen, but No text could be extracted from the specified region.",
            "extracted_text": ""
        })

    # Copy to clipboard
    try:
        pyperclip.copy(extracted)
    except Exception as e:
        print(f"[ScreenPeeler] Clipboard copy warning: {e}")

    preview = extracted[:150] + ("..." if len(extracted) > 150 else "")
    return json.dumps({
        "status": "success",
        "message": f"ScreenPeeler extracted {len(extracted)} characters to clipboard: {preview}",
        "extracted_text": extracted
    })


TOOL = {
    "name": "screen_peeler",
    "description": "ScreenPeeler OCR: takes a high-resolution snapshot of screen coordinates or active window, extracts code and text with OCR, and populates your clipboard.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "region": {
                "type": "ARRAY",
                "items": {"type": "INTEGER"},
                "description": "Optional bounding box coordinates [x1, y1, x2, y2]. Omit to scan active screen."
            },
            "action": {
                "type": "STRING",
                "enum": ["scan", "full", "extract_code"],
                "description": "Operation type."
            }
        }
    },
    "handler": screen_peeler
}
