"""Isolated Dynamic Scratch Sandbox & Script Evaluator for Zaya.
Created and developed by Sajan Rai.

Provides safe, bounded, temporary evaluation of Python snippets, data transforms,
and mathematical algorithms with output capture and automatic lifecycle cleanup.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

_DEFAULT_SCRATCH_DIR = mutable_path(Path(__file__).resolve().parent.parent / "memory" / "scratch_sandbox")


@dataclass
class EvalResult:
    language: str
    status: str  # success, error, timeout
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    scratch_file: Optional[str] = None


class ScratchSandbox:
    """Bounded, isolated scratch code execution environment."""

    DEFAULT_TIMEOUT_SEC = 5.0
    MAX_TIMEOUT_SEC = 30.0

    def __init__(self, scratch_dir: Optional[Path] = None) -> None:
        self.scratch_dir = scratch_dir or _DEFAULT_SCRATCH_DIR
        self.scratch_dir.mkdir(parents=True, exist_ok=True)

    def eval_python(
        self,
        code: str,
        timeout: float = DEFAULT_TIMEOUT_SEC,
        cleanup: bool = True,
    ) -> EvalResult:
        """Execute a Python snippet in an isolated subprocess with captured IO."""
        bounded_timeout = min(max(0.5, timeout), self.MAX_TIMEOUT_SEC)
        snippet = code.strip()
        if not snippet:
            return EvalResult(
                language="python",
                status="error",
                stdout="",
                stderr="Provided code is empty.",
                exit_code=-1,
                duration_ms=0.0,
            )

        timestamp_id = int(time.time() * 1000)
        script_file = self.scratch_dir / f"scratch_{timestamp_id}.py"

        try:
            script_file.write_text(snippet, encoding="utf-8")
            start_t = time.perf_counter()

            # Run using the active virtual environment Python
            python_exe = sys.executable

            proc = subprocess.run(
                [python_exe, "-u", str(script_file)],
                cwd=str(self.scratch_dir),
                capture_output=True,
                text=True,
                timeout=bounded_timeout,
            )
            duration_ms = (time.perf_counter() - start_t) * 1000.0

            status = "success" if proc.returncode == 0 else "error"
            return EvalResult(
                language="python",
                status=status,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                exit_code=proc.returncode,
                duration_ms=round(duration_ms, 2),
                scratch_file=str(script_file) if not cleanup else None,
            )

        except subprocess.TimeoutExpired as exc:
            duration_ms = bounded_timeout * 1000.0
            return EvalResult(
                language="python",
                status="timeout",
                stdout=str(exc.stdout or "").strip(),
                stderr=f"Execution timed out after {bounded_timeout:.1f} seconds.",
                exit_code=-1,
                duration_ms=round(duration_ms, 2),
                scratch_file=str(script_file) if not cleanup else None,
            )
        except Exception as exc:
            return EvalResult(
                language="python",
                status="error",
                stdout="",
                stderr=f"Sandbox execution error: {exc}",
                exit_code=-1,
                duration_ms=0.0,
                scratch_file=str(script_file) if not cleanup else None,
            )
        finally:
            if cleanup and script_file.exists():
                try:
                    script_file.unlink()
                except Exception:
                    pass

    def clean_scratch(self) -> int:
        """Purge all temporary scratch files in the sandbox directory."""
        purged = 0
        if self.scratch_dir.exists():
            for item in self.scratch_dir.glob("scratch_*"):
                try:
                    if item.is_file():
                        item.unlink()
                        purged += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        purged += 1
                except Exception:
                    pass
        return purged


_sandbox: Optional[ScratchSandbox] = None


def get_scratch_sandbox() -> ScratchSandbox:
    global _sandbox
    if _sandbox is None:
        _sandbox = ScratchSandbox()
    return _sandbox
