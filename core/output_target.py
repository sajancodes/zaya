"""Output target models and destination intent resolution.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class OutputTarget:
    modality: str      # "visual", "media", "audio", "file"
    destination: str   # "zaya_display", "browser", "filesystem", "speaker"
    format: str        # "text", "markdown", "code", "list", "video", "xlsx", "txt", "pdf"
    persistent: bool = False

    def is_display(self) -> bool:
        return self.destination == "zaya_display"

    def is_file(self) -> bool:
        return self.destination == "filesystem" or self.persistent

    def is_media(self) -> bool:
        return self.modality == "media" or self.format in ("video", "audio")


# Keywords indicating file creation/saving on filesystem
_FILE_KEYWORDS = (
    r"\b(save|export|download|write to (a )?file|make an? excel|create an? excel|spreadsheet|"
    r"save (this )?on desktop|write to disk|make a pdf|create a doc(ument)?|generate document|"
    r"\.xlsx|\.docx|\.pdf|\.csv|\.txt\b)"
)

# Keywords indicating visual display in Zaya UI
_DISPLAY_KEYWORDS = (
    r"\b(display|screen|show (it|me|this|that|all)?|put (it|this|that|all)? on (my |the )?(display|screen)|"
    r"write (it|this|that|all)? on (my |the )?(display|screen)|give me this visually|"
    r"result window|content panel|visual(ly)?|show the results?|render)\b"
)

# Keywords indicating video/audio playback
_MEDIA_KEYWORDS = (
    r"\b(play|watch|video|trailer|song|youtube|track|clip|listen to)\b"
)


def resolve_output_targets(text: str) -> List[OutputTarget]:
    """Resolves output targets from an owner's request.
    Supports single or multiple targets (e.g. create Excel AND show summary on display).
    """
    t = text.lower().strip()
    targets: List[OutputTarget] = []

    has_file = bool(re.search(_FILE_KEYWORDS, t))
    has_display = bool(re.search(_DISPLAY_KEYWORDS, t))
    has_media = bool(re.search(_MEDIA_KEYWORDS, t))

    if has_file:
        fmt = "xlsx" if ("excel" in t or "spreadsheet" in t or ".xlsx" in t) else ("pdf" if "pdf" in t else "text")
        targets.append(OutputTarget(
            modality="file",
            destination="filesystem",
            format=fmt,
            persistent=True,
        ))

    if has_media and not has_file:
        targets.append(OutputTarget(
            modality="media",
            destination="browser" if "browser" in t else "zaya_display",
            format="video",
            persistent=False,
        ))
    elif has_display or not targets:
        # Default for visual/text intent
        targets.append(OutputTarget(
            modality="visual",
            destination="zaya_display",
            format="text",
            persistent=False,
        ))

    return targets
