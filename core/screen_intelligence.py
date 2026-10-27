"""Zaya Screen Vision & App Intelligence Engine.
Privacy-conscious screen understanding, local OCR/text analysis,
question answering, sensitive data redaction, and prompt injection defense.
"""
from __future__ import annotations

import io
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core import audit


@dataclass
class ScreenElement:
    text: str
    element_type: str = "text"  # "button", "text", "input", "checkbox", "image"
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, right, bottom
    is_interactive: bool = False
    is_consequential: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScreenAnalysisRequest:
    prompt: str = "What is on my screen?"
    text_content: str | None = None
    structured_elements: list[ScreenElement] = field(default_factory=list)
    image_bytes: bytes | None = None
    package_name: str | None = None
    window_title: str | None = None
    has_secure_fields: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreenAnalysisResult:
    status: str  # "success", "failed", "permission_required"
    summary: str
    extracted_text: str = ""
    error_detected: str | None = None
    highlighted_controls: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    provider: str = "local_intelligence"
    has_secure_fields: bool = False
    cleaned_up: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


CONSEQUENTIAL_KEYWORDS = {
    "buy", "purchase", "pay", "payment", "delete", "remove",
    "clear", "wipe", "transfer", "submit", "confirm", "send",
    "order", "checkout", "subscribe", "reboot", "factory reset"
}

ERROR_PATTERNS = [
    re.compile(r"(?i)\b(?:error|exception|failure|failed|crash|unable to|denied|fatal|timed out|404|500)\b"),
    re.compile(r"(?i)\b(?:cannot connect|network error|permission denied|invalid credential|authentication failed)\b"),
]

# Prompt injection markers inside untrusted screen/web text
INJECTION_MARKERS = [
    re.compile(r"(?i)\[system\s*(?:instruction|override|prompt|command)[^\]]*\]"),
    re.compile(r"(?i)ignore\s+(?:all\s+)?previous\s+instructions.*"),
    re.compile(r"(?i)new\s+system\s+directive:.*"),
    re.compile(r"(?i)(?:format|wipe|delete)\s+(?:phone|device|system|all\s+files).*"),
]


class ScreenIntelligenceEngine:
    """Understands visible screen content, summarizes pages, detects error messages,
    locates interactive controls, redacts sensitive text, and isolates untrusted inputs.
    """

    def __init__(self, vision_model_client: Any = None) -> None:
        self.vision_model_client = vision_model_client

    def disarm_untrusted_content(self, text: str) -> str:
        """Strips or neutralizes prompt injection instructions attempting to override assistant rules."""
        cleaned = text
        for pat in INJECTION_MARKERS:
            cleaned = pat.sub("[Untrusted content neutralized]", cleaned)
        return cleaned

    def sanitize_text(self, text: str) -> str:
        """Redacts credentials, private keys, payment numbers, and disarms prompt injection."""
        # Redact credit card numbers
        text = re.sub(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', '[REDACTED]', text)
        # Redact PIN codes
        text = re.sub(r'(?i)\b(pin|cvv|cvc)\s*(?:code)?\s*[:=]?\s*\d+\b', r'\1: [REDACTED]', text)
        # Redact API keys with spaces or underscores, e.g. "API key: ..."
        text = re.sub(r'(?i)\b(?:api[_\s-]?key|token|secret|password|bearer)\s*[:=]\s*[^\s,;]+', '[REDACTED]', text)
        text = re.sub(r'\bAIza[\w-]{15,}\b', '[REDACTED]', text)
        safe_data = audit.redact(text)
        return self.disarm_untrusted_content(safe_data)

    def analyze_screen(self, request: ScreenAnalysisRequest) -> ScreenAnalysisResult:
        """Processes screen content and answers user questions safely."""
        image_bytes = request.image_bytes
        try:
            return self._analyze_screen_internal(request)
        finally:
            # Enforce immediate cleanup of raw frame buffer from memory
            if image_bytes is not None:
                del image_bytes
                request.image_bytes = None

    def _analyze_screen_internal(self, request: ScreenAnalysisRequest) -> ScreenAnalysisResult:
        # Check explicit revocation / denial metadata
        if request.metadata.get('permission_denied'):
            return ScreenAnalysisResult(
                status="failed",
                summary="Screen capture or accessibility authorization is required.",
                extracted_text="",
                confidence=0.0,
            )
        if request.metadata.get('revoked'):
            return ScreenAnalysisResult(
                status="failed",
                summary="Screen capture authorization was revoked or denied.",
                extracted_text="",
                confidence=0.0,
            )

        # 1. Validation: check if any screen data is available
        has_text = request.text_content is not None
        has_elements = bool(request.structured_elements)
        has_image = bool(request.image_bytes and len(request.image_bytes) > 0)

        if not has_text and not has_elements and not has_image:
            return ScreenAnalysisResult(
                status="failed",
                summary="No screen data provided. Screen capture or accessibility authorization is required.",
                extracted_text="",
                confidence=0.0,
            )

        # 2. Extract and sanitize raw text from structured elements or text buffer
        text_lines: list[str] = []
        controls: list[dict[str, Any]] = []

        if request.text_content:
            sanitized_input = self.sanitize_text(request.text_content)
            for line in sanitized_input.splitlines():
                if line.strip():
                    text_lines.append(line.strip())

        for elem in request.structured_elements:
            sanitized_elem_text = self.sanitize_text(elem.text)
            if sanitized_elem_text:
                text_lines.append(sanitized_elem_text)
            if elem.is_interactive:
                words = sanitized_elem_text.lower().split()
                is_consequential = any(w in CONSEQUENTIAL_KEYWORDS for w in words) or elem.is_consequential
                controls.append({
                    'label': sanitized_elem_text,
                    'type': elem.element_type,
                    'bounds': elem.bounds,
                    'consequential': is_consequential,
                })

        full_text = "\n".join(text_lines).strip()
        sanitized_full_text = self.sanitize_text(full_text)

        # 3. Secure input notification
        if request.has_secure_fields:
            secure_note = " (Note: Secure/password input fields were detected and omitted for your privacy.)"
        else:
            secure_note = ""

        # Check for unreadable/empty text with no elements
        if not text_lines and not controls:
            return ScreenAnalysisResult(
                status="success",
                summary=f"Visible screen captured, but no readable text was detected.{secure_note}",
                extracted_text="",
                confidence=0.5,
                has_secure_fields=request.has_secure_fields,
            )

        # 4. Error detection
        detected_error: str | None = None
        for line in text_lines:
            for pat in ERROR_PATTERNS:
                if pat.search(line):
                    detected_error = line.strip()
                    break
            if detected_error:
                break

        query = request.prompt.lower().strip()

        # 5. Question Answering Logic
        # A. Error Explanation
        if "error" in query or "problem" in query or "failed" in query:
            if detected_error:
                summary = f"Detected error message: \"{detected_error}\".{secure_note}"
            else:
                summary = f"No obvious error message was detected on the visible screen.{secure_note}"

            return ScreenAnalysisResult(
                status="success",
                summary=summary,
                extracted_text=sanitized_full_text,
                error_detected=detected_error,
                highlighted_controls=controls,
                has_secure_fields=request.has_secure_fields,
            )

        # B. Control / Button Search
        if "find" in query or "button" in query or "click" in query or "where" in query:
            clean_target = re.sub(r"(?i)\b(?:find|locate|where\s+is|button\s+for|button\s+to|button|the|click)\b", "", query).strip()
            if not clean_target:
                clean_target = query

            matching_control = None
            for ctrl in controls:
                label_lower = ctrl['label'].lower()
                if clean_target in label_lower or any(part in label_lower for part in clean_target.split() if len(part) > 2):
                    matching_control = ctrl
                    break

            if matching_control:
                conseq_msg = " [Requires confirmation before action]" if matching_control['consequential'] else ""
                summary = f"Found matching control: \"{matching_control['label']}\" ({matching_control['type']}){conseq_msg}.{secure_note}"
                return ScreenAnalysisResult(
                    status="success",
                    summary=summary,
                    extracted_text=sanitized_full_text,
                    highlighted_controls=[matching_control],
                    has_secure_fields=request.has_secure_fields,
                )
            else:
                summary = f"Could not find a visible control matching '{clean_target}'.{secure_note}"
                return ScreenAnalysisResult(
                    status="success",
                    summary=summary,
                    extracted_text=sanitized_full_text,
                    highlighted_controls=[],
                    has_secure_fields=request.has_secure_fields,
                )

        # C. Page Summarization
        if "summarize" in query or "summary" in query or "what is" in query:
            app_context = f"in {request.package_name}" if request.package_name else ""
            if text_lines:
                preview = "; ".join(text_lines[:4])
                summary = f"Screen view {app_context}: {preview}. Total {len(text_lines)} text items visible.{secure_note}"
            else:
                summary = f"Screen view {app_context}: Interactive canvas visible with {len(controls)} controls.{secure_note}"

            return ScreenAnalysisResult(
                status="success",
                summary=summary,
                extracted_text=sanitized_full_text,
                error_detected=detected_error,
                highlighted_controls=controls,
                has_secure_fields=request.has_secure_fields,
            )

        # D. General Text Reading / Fallback
        if not sanitized_full_text:
            return ScreenAnalysisResult(
                status="success",
                summary=f"Visible screen captured, but no readable text was detected.{secure_note}",
                extracted_text="",
                confidence=0.5,
                has_secure_fields=request.has_secure_fields,
            )

        return ScreenAnalysisResult(
            status="success",
            summary=f"Read {len(text_lines)} text lines from screen.{secure_note}",
            extracted_text=sanitized_full_text,
            error_detected=detected_error,
            highlighted_controls=controls,
            has_secure_fields=request.has_secure_fields,
        )


_screen_intelligence: ScreenIntelligenceEngine | None = None


def get_screen_intelligence() -> ScreenIntelligenceEngine:
    global _screen_intelligence
    if _screen_intelligence is None:
        _screen_intelligence = ScreenIntelligenceEngine()
    return _screen_intelligence
