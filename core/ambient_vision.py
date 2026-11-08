"""Ambient Continuous Workspace Vision & Multi-Language Traceback Peeler for Zaya.
Created and developed by Sajan Rai.

Provides passive syntactic and semantic diagnostic analysis of compiler outputs,
stack traces, and runtime exceptions across Python, TypeScript, Kotlin, Rust, and Go.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, List, Optional

from core.project_awareness import get_project_awareness

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticFinding:
    language: str
    error_type: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    recommended_fix: str = ""
    confidence: float = 0.90


class WorkspaceErrorPeeler:
    """Parses and diagnoses compiler errors, exceptions, and stack traces."""

    def __init__(self) -> None:
        pass

    def parse_traceback(self, text: str) -> List[DiagnosticFinding]:
        """Parse raw terminal/compiler text into structured diagnostic findings."""
        if not text or not text.strip():
            return []

        findings: List[DiagnosticFinding] = []

        # 1. Python Traceback
        py_findings = self._parse_python(text)
        findings.extend(py_findings)

        # 2. TypeScript / JavaScript Error
        ts_findings = self._parse_typescript(text)
        findings.extend(ts_findings)

        # 3. Kotlin / Gradle Compiler Error
        kt_findings = self._parse_kotlin(text)
        findings.extend(kt_findings)

        # 4. Rust Compiler Error
        rs_findings = self._parse_rust(text)
        findings.extend(rs_findings)

        # 5. Go Panic / Compiler Error
        go_findings = self._parse_go(text)
        findings.extend(go_findings)

        return findings

    def _parse_python(self, text: str) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        # If Node/V8 stack traces are present ("at foo (bar:1:2)"), don't treat as Python
        if re.search(r"^\s*at\s+", text, re.MULTILINE):
            return findings

        # Pattern: File "path", line X, in Y \n ... \n ExceptionName: message
        py_trace_re = re.compile(
            r'File ["\'](?P<file>[^"\']+)["\'], line (?P<line>\d+)(?:, in (?P<func>\w+))?',
            re.MULTILINE,
        )
        exc_re = re.compile(
            r'^(?P<exc>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning|Interrupt|Exit)): (?P<msg>.+)$',
            re.MULTILINE,
        )

        matches = list(py_trace_re.finditer(text))
        exc_matches = list(exc_re.finditer(text))

        if matches and exc_matches:
            last_frame = matches[-1]
            last_exc = exc_matches[-1]
            file_p = last_frame.group("file")
            line_no = int(last_frame.group("line"))
            exc_name = last_exc.group("exc")
            msg = last_exc.group("msg").strip()

            fix = self._suggest_python_fix(exc_name, msg, file_p)
            findings.append(
                DiagnosticFinding(
                    language="python",
                    error_type=exc_name,
                    message=msg,
                    file_path=file_p,
                    line_number=line_no,
                    recommended_fix=fix,
                    confidence=0.95,
                )
            )
        elif exc_matches and not matches:
            # Standalone exception without full traceback
            last_exc = exc_matches[-1]
            exc_name = last_exc.group("exc")
            msg = last_exc.group("msg").strip()
            findings.append(
                DiagnosticFinding(
                    language="python",
                    error_type=exc_name,
                    message=msg,
                    recommended_fix=self._suggest_python_fix(exc_name, msg, None),
                    confidence=0.80,
                )
            )

        return findings

    def _suggest_python_fix(self, exc_name: str, msg: str, file_path: Optional[str]) -> str:
        if exc_name == "ImportError" or exc_name == "ModuleNotFoundError":
            mod_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", msg)
            if mod_match:
                return f"Install missing dependency via pip/uv: 'pip install {mod_match.group(1)}' or check PYTHONPATH."
            return "Verify import path or install the missing package in virtual environment."
        elif exc_name == "AttributeError":
            return "Verify attribute spelling or inspect object type before member access."
        elif exc_name == "KeyError":
            return "Use dict.get(key, default) or verify that key is populated before indexing."
        elif exc_name == "FileNotFoundError":
            return "Verify target file path exists or use absolute path / Path.resolve()."
        elif exc_name == "PermissionError":
            return "Verify file system permissions or run with elevated user trust."
        return f"Address {exc_name}: check referenced inputs and caller arguments."

    def _parse_typescript(self, text: str) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        # Pattern: TypeError: msg \n at func (file:line:col)
        ts_re = re.compile(
            r'(?:^\s*)?(?P<err>[A-Za-z]+Error): (?P<msg>[^\n]+)\n\s*at (?:[^\n]+ )?\(?(?P<file>[A-Za-z]:[^\n:]+|/[^\n:]+):(?P<line>\d+):(?P<col>\d+)\)?',
            re.MULTILINE,
        )
        for m in ts_re.finditer(text):
            err_type = m.group("err")
            msg = m.group("msg").strip()
            file_p = m.group("file")
            line_no = int(m.group("line"))
            findings.append(
                DiagnosticFinding(
                    language="typescript",
                    error_type=err_type,
                    message=msg,
                    file_path=file_p,
                    line_number=line_no,
                    recommended_fix=f"Examine {file_p}:{line_no} for null/undefined or type mismatch.",
                    confidence=0.92,
                )
            )
        return findings

    def _parse_kotlin(self, text: str) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        # Pattern: e: file:line:col message
        kt_re = re.compile(
            r'e:\s+(?P<file>[A-Za-z]:\\[^\n:]+|/[^\n:]+):(?P<line>\d+):(?P<col>\d+)\s+(?P<msg>.+)',
            re.MULTILINE,
        )
        for m in kt_re.finditer(text):
            file_p = m.group("file")
            line_no = int(m.group("line"))
            msg = m.group("msg").strip()
            findings.append(
                DiagnosticFinding(
                    language="kotlin",
                    error_type="CompilationError",
                    message=msg,
                    file_path=file_p,
                    line_number=line_no,
                    recommended_fix=f"Resolve Kotlin syntax or type mismatch in {Path(file_p).name}:{line_no}.",
                    confidence=0.95,
                )
            )
        return findings

    def _parse_rust(self, text: str) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        # Pattern: error[E0000]: msg \n --> file:line:col
        rs_re = re.compile(
            r'error(?:\[(?P<code>E\d+)\])?:\s+(?P<msg>[^\n]+)\n\s+-->\s+(?P<file>[^\n:]+):(?P<line>\d+):(?P<col>\d+)',
            re.MULTILINE,
        )
        for m in rs_re.finditer(text):
            code = m.group("code") or "CompileError"
            msg = m.group("msg").strip()
            file_p = m.group("file")
            line_no = int(m.group("line"))
            findings.append(
                DiagnosticFinding(
                    language="rust",
                    error_type=code,
                    message=msg,
                    file_path=file_p,
                    line_number=line_no,
                    recommended_fix=f"Inspect rustc diagnostic {code} at {file_p}:{line_no}.",
                    confidence=0.96,
                )
            )
        return findings

    def _parse_go(self, text: str) -> List[DiagnosticFinding]:
        findings: List[DiagnosticFinding] = []
        # Pattern: panic: msg \n ... \n file:line +0x...
        go_panic_re = re.compile(
            r'panic:\s+(?P<msg>[^\n]+)\n\n(?:goroutine \d+ [^\n]+:\n)?(?:\t?[^\n]+\n\t(?P<file>[^\n:]+):(?P<line>\d+))?',
            re.MULTILINE,
        )
        for m in go_panic_re.finditer(text):
            msg = m.group("msg").strip()
            file_p = m.group("file")
            line_no = int(m.group("line")) if m.group("line") else None
            findings.append(
                DiagnosticFinding(
                    language="go",
                    error_type="Panic",
                    message=msg,
                    file_path=file_p,
                    line_number=line_no,
                    recommended_fix="Handle runtime panic or nil pointer dereference with recover/guards.",
                    confidence=0.90,
                )
            )
        return findings

    def diagnose(self, text: str, project_name: str = "") -> dict[str, Any]:
        """Provide a complete ambient diagnostic summary and correlation."""
        findings = self.parse_traceback(text)
        awareness = get_project_awareness()
        snapshot = awareness.snapshot()

        active_proj = project_name or snapshot.get("active_project", "")
        summary_parts = []

        if not findings:
            return {
                "has_errors": False,
                "summary": "No compiler errors or stack traces detected in output.",
                "findings": [],
                "project": active_proj,
            }

        primary = findings[0]
        loc_str = f" in {primary.file_path}:{primary.line_number}" if primary.file_path and primary.line_number else ""
        summary_parts.append(
            f"Detected {primary.language.title()} {primary.error_type}{loc_str}: {primary.message}."
        )
        if primary.recommended_fix:
            summary_parts.append(f"Recommendation: {primary.recommended_fix}")

        return {
            "has_errors": True,
            "summary": " ".join(summary_parts),
            "findings": [asdict(f) for f in findings],
            "project": active_proj,
        }


_peeler: Optional[WorkspaceErrorPeeler] = None


def get_error_peeler() -> WorkspaceErrorPeeler:
    global _peeler
    if _peeler is None:
        _peeler = WorkspaceErrorPeeler()
    return _peeler
