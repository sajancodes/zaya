"""ScreenPeeler AI OCR: Intelligent rectangular region screen selection & text extraction.
Created and developed by Sajan Rai for Zaya.

Takes a snapshot of screen coordinates or active window, runs OCR extraction,
and populates the extracted text directly to the clipboard.
"""
from __future__ import annotations

import io
import base64
import subprocess
import sys
from typing import List, Optional

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False

from core.execution_policy import require_owner
from core.tool_result import ToolResult


def capture_screen_region(region: Optional[List[int]] = None) -> Optional[bytes]:
    """Captures a screen region [x1, y1, x2, y2]. If None, captures entire primary screen.

    Returns PNG image bytes.
    """
    if not _MSS:
        return None

    try:
        with mss.mss() as sct:
            monitors = sct.monitors
            target = monitors[1] if len(monitors) > 1 else monitors[0]

            if region and len(region) >= 4:
                x1, y1, x2, y2 = region[0], region[1], region[2], region[3]
                monitor = {
                    "left": int(min(x1, x2)),
                    "top": int(min(y1, y2)),
                    "width": max(1, int(abs(x2 - x1))),
                    "height": max(1, int(abs(y2 - y1)))
                }
            else:
                monitor = target

            shot = sct.grab(monitor)
            return mss.tools.to_png(shot.rgb, shot.size)
    except Exception:
        return None


def _ocr_via_powershell(png_bytes: bytes) -> str:
    """Uses Windows.Media.Ocr via PowerShell (native Windows 10/11 built-in, no external binaries)."""
    if sys.platform != "win32":
        return ""

    try:
        ps_script = """
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
        Function Await($WinRtTask, $ResultType) {
            $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
            $netTask = $asTask.Invoke($null, @($WinRtTask))
            $netTask.Wait(-1) | Out-Null
            $netTask.Result
        }
        [Windows.Globalization.Language,Windows.Foundation.Diagnostics,ContentType=WindowsRuntime] | Out-Null
        [Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation.Diagnostics,ContentType=WindowsRuntime] | Out-Null
        [Windows.Media.Ocr.OcrEngine,Windows.Foundation.Diagnostics,ContentType=WindowsRuntime] | Out-Null

        [Windows.Storage.Streams.InMemoryRandomAccessStream,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
        [Windows.Storage.Streams.DataWriter,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
        $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
        $writer = New-Object Windows.Storage.Streams.DataWriter($stream)
        $writer.WriteBytes([Convert]::FromBase64String([Console]::In.ReadToEnd()))
        Await ($writer.StoreAsync()) ([uint32]) | Out-Null
        $writer.DetachStream() | Out-Null
        $stream.Seek(0)
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
        $ocrResult = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $ocrResult.Text
        """
        # An image never touches disk. Data is stdin, never executable script.
        res = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            input=base64.b64encode(png_bytes).decode('ascii'),capture_output=True,text=True,timeout=8,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
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

    text = _ocr_via_powershell(png)
    if text:
        return text

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


def screen_peeler(parameters: dict, **_kwargs) -> ToolResult:
    """ScreenPeeler Action: Captures screen region, extracts code/text, and copies directly to clipboard."""
    require_owner()
    region = parameters.get("region")
    source = str(parameters.get('source') or ('coordinates' if region is not None else 'full_monitor'))
    if region is None and source != 'full_monitor':
        from core.perception.roi_tracker import resolve_region
        from core.perception.screen_perception import perception
        try:
            region = resolve_region(source,perception.snapshot())
        except ValueError as error:
            return ToolResult('failed',str(error))

    extracted = extract_text_from_region(region)
    if not extracted:
        return ToolResult(
            "failed",
            "ScreenPeeler captured the screen, but no text could be extracted from the specified region.",
            data={"extracted_text": ""}
        )

    copied = False
    if _PYPERCLIP:
        try:
            pyperclip.copy(extracted)
            copied = True
        except Exception:
            pass

    preview = extracted[:150] + ("..." if len(extracted) > 150 else "")
    return ToolResult(
        "success" if copied else "partial",
        (f"ScreenPeeler copied {len(extracted)} characters to the clipboard: {preview}" if copied else
         f"ScreenPeeler extracted {len(extracted)} characters, but could not update the clipboard: {preview}"),
        data={"extracted_text": extracted, "length": len(extracted), "copied_to_clipboard": copied, 'region':region,'source':source},
        side_effect=copied
    )


TOOL = {
    "name": "screen_peeler",
    "description": "ScreenPeeler OCR: takes a snapshot of screen coordinates or active window, extracts code and text with OCR, and populates your clipboard.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "source": {"type":"STRING","enum":["coordinates","cursor","active_window","tracked_roi","full_monitor"]},
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
