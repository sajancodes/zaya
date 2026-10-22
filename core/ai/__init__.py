"""Shared AI engine contracts for Zaya.

The live and modular engines expose the same small surface to the rest of Zaya:
a session-like text/audio input, the standard tool event contract, and explicit
readiness. Provider details stay below this package.
"""

from core.ai.capabilities import EngineCapabilities, GEMINI_LIVE_CAPABILITIES, local_pipeline_capabilities
from core.ai.settings import (
    engine_mode,
    save_engine_mode,
    local_pipeline_settings,
    readiness_path,
)

__all__ = [
    "EngineCapabilities",
    "GEMINI_LIVE_CAPABILITIES",
    "local_pipeline_capabilities",
    "engine_mode",
    "save_engine_mode",
    "local_pipeline_settings",
    "readiness_path",
]
