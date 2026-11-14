"""Toolsmith Engine — Dynamic Tool Synthesis & Runtime Plugin Compiler.
Created and developed by Sajan Rai for Zaya.

Enables autonomous synthesis, AST security validation, dry-run sandbox testing,
and dynamic live registration of new tools into Zaya's ActionRegistry on the fly.
"""
from __future__ import annotations

import ast
import json
import logging
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.action_loader import ActionRecord, get_action_registry
from core.execution_policy import require_owner
from core.runtime_paths import mutable_path

logger = logging.getLogger(__name__)

# Security: strict import allowlist for synthesized tools
_ALLOWED_MODULES = {
    "math",
    "datetime",
    "time",
    "json",
    "re",
    "string",
    "collections",
    "itertools",
    "functools",
    "dataclasses",
    "typing",
    "urllib.parse",
    "hashlib",
    "random",
    "base64",
    "uuid",
}

_FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "__import__",
    "compile",
    "open",
    "input",
}

_FORBIDDEN_ATTRS = {
    "__subclasses__",
    "__bases__",
    "__mro__",
    "__globals__",
    "__code__",
    "__builtins__",
    "f_globals",
    "f_locals",
    "f_builtins",
    "gi_frame",
}


@dataclass
class SynthesizedToolMeta:
    name: str
    description: str
    code: str
    created_at: float
    test_cases: List[Dict[str, Any]] = field(default_factory=list)
    file_path: Optional[str] = None
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "code": self.code,
            "created_at": self.created_at,
            "file_path": self.file_path,
            "enabled": self.enabled,
            "test_cases": self.test_cases,
        }


class ToolsmithEngine:
    """Manages the creation, validation, dynamic loading, and lifecycle of synthesized tools."""

    def __init__(self, custom_tools_dir: Optional[Path] = None) -> None:
        if custom_tools_dir is None:
            self.tools_dir = mutable_path(Path("actions") / "custom")
        else:
            self.tools_dir = custom_tools_dir
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self._meta_file = self.tools_dir / "_toolsmith_catalog.json"
        self._tools: Dict[str, SynthesizedToolMeta] = {}
        self._lock = threading.RLock()
        self._load_catalog()

    def _load_catalog(self) -> None:
        with self._lock:
            if not self._meta_file.exists():
                return
            try:
                data = json.loads(self._meta_file.read_text(encoding="utf-8"))
                for item in data:
                    meta = SynthesizedToolMeta(**item)
                    self._tools[meta.name] = meta
            except Exception as e:
                logger.warning("[Toolsmith] Failed to load catalog: %s", e)

    def _save_catalog(self) -> None:
        with self._lock:
            try:
                data = [t.to_dict() for t in self._tools.values()]
                self._meta_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as e:
                logger.error("[Toolsmith] Failed to save catalog: %s", e)

    def validate_code_safety(self, code: str) -> Tuple[bool, str]:
        """Perform static analysis on tool code to prevent unsafe operations."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error in code: {e}"

        for node in ast.walk(tree):
            # Enforce import allowlist
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if alias.name not in _ALLOWED_MODULES and root not in _ALLOWED_MODULES:
                        return False, f"Import '{alias.name}' is not in the approved safe modules list."
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    if node.module not in _ALLOWED_MODULES and root not in _ALLOWED_MODULES:
                        return False, f"From-import '{node.module}' is not in the approved safe modules list."

            # Check forbidden calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in _FORBIDDEN_CALLS:
                        return False, f"Forbidden built-in call '{node.func.id}()' is not allowed."
                    if node.func.id == "getattr":
                        return False, "Dynamic attribute inspection via getattr() is forbidden."

            # Check forbidden attribute escapes
            elif isinstance(node, ast.Attribute):
                if node.attr in _FORBIDDEN_ATTRS or node.attr.startswith("__"):
                    return False, f"Access to sensitive or dunder attribute '{node.attr}' is forbidden."

        # Verify TOOL dictionary declaration exists in AST
        tool_decl_found = False
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "TOOL":
                        tool_decl_found = True
                        break
        if not tool_decl_found:
            return False, "Code must define a module-level 'TOOL' dictionary."

        return True, "Code passed security and structural validation."

    def synthesize_tool(
        self,
        name: str,
        code: str,
        description: str = "",
        test_args: Optional[Dict[str, Any]] = None,
        overwrite: bool = True,
    ) -> Tuple[bool, str, Optional[SynthesizedToolMeta]]:
        """Synthesize, validate, test, and register a new tool."""
        require_owner()

        # Sanitize tool name
        name = name.strip()
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$", name):
            return False, f"Invalid tool name '{name}'. Must be alphanumeric identifier.", None

        # 1. Static AST Safety check
        safe, reason = self.validate_code_safety(code)
        if not safe:
            return False, f"Security check failed: {reason}", None

        # 2. Write tool to file
        file_path = self.tools_dir / f"{name}.py"
        try:
            file_path.write_text(code, encoding="utf-8")
        except Exception as e:
            return False, f"Failed to write tool file: {e}", None

        # 3. Dry-run load into temporary execution scope to verify
        namespace: Dict[str, Any] = {}
        try:
            compiled = compile(code, str(file_path), "exec")
            exec(compiled, namespace)
        except Exception as e:
            file_path.unlink(missing_ok=True)
            return False, f"Compilation/Runtime error during import: {e}", None

        tool_dict = namespace.get("TOOL")
        if not isinstance(tool_dict, dict):
            file_path.unlink(missing_ok=True)
            return False, "'TOOL' must be a dictionary.", None

        handler = tool_dict.get("handler")
        if not callable(handler):
            file_path.unlink(missing_ok=True)
            return False, "'TOOL['handler']' must be a callable function.", None

        # 4. Dry-run test execution
        if test_args is not None:
            try:
                test_result = handler(test_args)
                logger.info("[Toolsmith] Dry-run test succeeded for '%s': %s", name, str(test_result)[:80])
            except Exception as e:
                file_path.unlink(missing_ok=True)
                return False, f"Dry-run test failed with provided arguments: {e}", None

        # 5. Live register into ActionRegistry
        reg = get_action_registry()
        try:
            rec = reg.load_action_file(file_path, allow_replace=overwrite)
            if not rec:
                file_path.unlink(missing_ok=True)
                return False, "ActionRegistry rejected tool registration.", None
        except Exception as e:
            file_path.unlink(missing_ok=True)
            return False, f"Failed to register into ActionRegistry: {e}", None

        # 6. Save metadata
        meta = SynthesizedToolMeta(
            name=name,
            description=description or tool_dict.get("description", ""),
            code=code,
            created_at=time.time(),
            test_cases=[test_args] if test_args else [],
            file_path=str(file_path),
            enabled=True,
        )
        with self._lock:
            self._tools[name] = meta
            self._save_catalog()

        return True, f"Tool '{name}' successfully synthesized and dynamically registered.", meta

    def remove_tool(self, name: str) -> bool:
        """Unregister and remove a synthesized tool."""
        require_owner()
        with self._lock:
            meta = self._tools.pop(name, None)
            if not meta:
                return False

            # Unregister from ActionRegistry
            reg = get_action_registry()
            reg.unregister_action(name)

            # Delete file
            if meta.file_path:
                Path(meta.file_path).unlink(missing_ok=True)

            self._save_catalog()
            return True

    def list_tools(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [t.to_dict() for t in self._tools.values()]

    def get_tool(self, name: str) -> Optional[SynthesizedToolMeta]:
        with self._lock:
            return self._tools.get(name)


# ── Global Singleton ─────────────────────────────────────────────────────────

_toolsmith: Optional[ToolsmithEngine] = None


def get_toolsmith_engine() -> ToolsmithEngine:
    global _toolsmith
    if _toolsmith is None:
        _toolsmith = ToolsmithEngine()
    return _toolsmith
