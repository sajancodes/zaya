"""Visual UI Graph & Actionable Screen Click Anchors.
Created and developed by Sajan Rai for Zaya.

Constructs an interactive spatial UI element graph from screen OCR/UI elements,
assigning unambiguous, numbered visual click anchors to interactable controls.
Eliminates coordinate guesswork for desktop UI automation.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class UIAnchor:
    id: int
    label: str
    element_type: str  # button, input, tab, link, menu, icon, text
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    center: Tuple[int, int]
    confidence: float = 1.0
    parent_id: Optional[int] = None
    children: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "element_type": self.element_type,
            "bbox": list(self.bbox),
            "center": list(self.center),
            "confidence": round(self.confidence, 2),
        }


class VisualUIGraph:
    """Manages the current screen's spatial UI graph and numbered anchors."""

    def __init__(self) -> None:
        self._anchors: Dict[int, UIAnchor] = {}
        self._next_id: int = 1
        self._screen_size: Tuple[int, int] = (1920, 1080)

    def clear(self) -> None:
        self._anchors.clear()
        self._next_id = 1

    def build_from_elements(
        self,
        elements: List[Dict[str, Any]],
        screen_size: Tuple[int, int] = (1920, 1080),
    ) -> List[UIAnchor]:
        """Ingest detected UI elements / OCR spans and build the indexed UI graph.
        
        Expected element schema:
        {"label": str, "bbox": [x, y, w, h], "type": str (optional), "confidence": float}
        """
        self.clear()
        self._screen_size = screen_size

        for el in elements:
            label = str(el.get("label", "")).strip()
            if not label:
                continue
            bbox = el.get("bbox", [0, 0, 0, 0])
            if len(bbox) != 4:
                continue
            x, y, w, h = bbox
            cx = int(x + w / 2)
            cy = int(y + h / 2)
            etype = el.get("type", self._infer_element_type(label, w, h))
            conf = float(el.get("confidence", 1.0))

            anchor = UIAnchor(
                id=self._next_id,
                label=label,
                element_type=etype,
                bbox=(int(x), int(y), int(w), int(h)),
                center=(cx, cy),
                confidence=conf,
            )
            self._anchors[anchor.id] = anchor
            self._next_id += 1

        return list(self._anchors.values())

    def _infer_element_type(self, label: str, w: int, h: int) -> str:
        low = label.lower()
        if any(w in low for w in ("ok", "cancel", "submit", "save", "apply", "close", "yes", "no", "start", "stop")):
            return "button"
        if any(w in low for w in ("search", "find", "enter", "type", "http", "www")):
            return "input"
        if any(w in low for w in ("file", "edit", "view", "help", "window", "options")):
            return "menu"
        if w < 40 and h < 40:
            return "icon"
        return "text"

    def find_anchor(self, query: str) -> Optional[UIAnchor]:
        """Find the most relevant UI anchor matching a natural language query or numeric ID."""
        clean = query.strip()
        if clean.isdigit():
            aid = int(clean)
            return self._anchors.get(aid)

        low = clean.lower()
        best_anchor: Optional[UIAnchor] = None
        best_score = -1.0

        for anchor in self._anchors.values():
            a_label = anchor.label.lower()
            if a_label == low:
                return anchor  # Exact match
            if low in a_label:
                score = len(low) / float(len(a_label) + 1)
                if score > best_score:
                    best_score = score
                    best_anchor = anchor

        return best_anchor

    def get_anchors_summary(self, max_items: int = 50) -> List[Dict[str, Any]]:
        """Return a structured summary of active anchors for model prompting."""
        items = list(self._anchors.values())[:max_items]
        return [a.to_dict() for a in items]

    def resolve_click_target(self, target: str) -> Tuple[bool, Optional[Tuple[int, int]], str]:
        """Resolve a target (by anchor ID or label) to (x, y) coordinates with sanity checks."""
        anchor = self.find_anchor(target)
        if not anchor:
            return False, None, f"No interactive anchor found matching '{target}'."

        cx, cy = anchor.center
        sw, sh = self._screen_size
        if cx < 0 or cx >= sw or cy < 0 or cy >= sh:
            return False, None, f"Anchor #{anchor.id} coordinates ({cx}, {cy}) outside screen bounds."

        return True, (cx, cy), f"Resolved Anchor #{anchor.id} ('{anchor.label}') at ({cx}, {cy})."


# ── Global Singleton ─────────────────────────────────────────────────────────

_ui_graph: Optional[VisualUIGraph] = None


def get_visual_ui_graph() -> VisualUIGraph:
    global _ui_graph
    if _ui_graph is None:
        _ui_graph = VisualUIGraph()
    return _ui_graph
