"""Real-time Web Customization / Reality Hacker.
Created and developed by Sajan Rai for Zaya.
Modify web pages in real-time by injecting custom styles and scripts to test interface variations
or transform websites into cyberpunk, terminal, or dark modes live.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.execution_policy import require_owner

THEME_PRESETS = {
    "cyberpunk": """
        body, html {
            background-color: #0b0f19 !important;
            color: #00ff66 !important;
            font-family: 'Courier New', Courier, monospace !important;
        }
        a, button {
            color: #00ffff !important;
            border: 1px solid #00ff66 !important;
            text-shadow: 0 0 5px #00ff66 !important;
        }
        div, section, article {
            border-color: #00ff66 !important;
        }
    """,
    "terminal": """
        body, html {
            background-color: #000000 !important;
            color: #33ff33 !important;
            font-family: monospace !important;
            letter-spacing: 0.5px !important;
        }
        * {
            box-shadow: none !important;
            border-radius: 0 !important;
        }
    """,
    "dark_mode": """
        html, body {
            background-color: #121212 !important;
            color: #e0e0e0 !important;
        }
        p, span, h1, h2, h3, h4, h5, h6 {
            color: #f5f5f5 !important;
        }
    """,
    "clean_editorial": """
        body {
            max-width: 780px !important;
            margin: 0 auto !important;
            font-family: Georgia, serif !important;
            line-height: 1.8 !important;
            color: #222 !important;
        }
    """
}


def generate_custom_theme_css(theme_name: str) -> str:
    """Returns CSS string for named preset or default dark mode."""
    return THEME_PRESETS.get(theme_name.lower().strip(), THEME_PRESETS["dark_mode"])


def inject_css_into_browser(css_content: str, script_content: Optional[str] = None) -> Dict[str, Any]:
    """Attempts to inject style and script into active browser session via browser_control."""
    try:
        from actions.browser_control import _registry
        with _registry._lock:
            sessions = list(_registry._sessions.values())
            active = _registry._active_browser
        if sessions:
            sessions.sort(key=lambda session: getattr(session, 'browser_name', '') != active)
            for session in sessions:
                if getattr(session, "_page", None):
                    # Bind the session now: a closure over the loop variable
                    # would read whatever the loop ended on if the coroutine
                    # were ever started later.
                    target = session

                    async def _inject(session=target):
                        if css_content:
                            await session._page.add_style_tag(content=css_content)
                        if script_content:
                            await session._page.add_script_tag(content=script_content)
                    session.run(_inject())
                    return {
                        "status": "success",
                        "applied": True,
                        "message": "Injected custom CSS/JS into active browser session.",
                    }
    except Exception as e:
        return {
            "status": "partial",
            "applied": False,
            "message": f"Browser injection failed; CSS was prepared but not applied: {e}",
        }

    return {
        "status": "partial",
        "applied": False,
        "message": "No active browser session — the CSS was prepared but not applied.",
    }


def web_customize(parameters: dict, **_kwargs) -> str:
    """Real-time Web Customization Action."""
    require_owner()
    theme = parameters.get("theme", "cyberpunk")
    custom_css = parameters.get("css", "")
    custom_js = parameters.get("js", "")

    css_to_inject = custom_css if custom_css else generate_custom_theme_css(theme)
    result = inject_css_into_browser(css_to_inject, custom_js)

    # "applied" is the authoritative answer to "did the page change?". The
    # old code always said "Applied <theme> styling to web session" even
    # when there was no session at all and nothing was injected.
    applied = bool(result.get("applied", result.get("status") == "success"))
    details = result.get("message", "")
    if applied:
        message = f"Applied {theme} styling to the active web session."
    else:
        message = f"Theme '{theme}' was prepared but NOT applied — {details}"

    return json.dumps({
        "status": "success" if applied else "partial",
        "theme": theme,
        "applied": applied,
        "message": message,
        "details": details
    }, indent=2)


TOOL = {
    "name": "web_customize",
    "description": "Real-time Web Customization: Visually mutate and inject custom CSS/JS into active websites (e.g. inject cyberpunk theme, terminal green, dark mode).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "theme": {
                "type": "STRING",
                "enum": ["cyberpunk", "terminal", "dark_mode", "clean_editorial"],
                "description": "Pre-configured aesthetic theme to inject."
            },
            "css": {
                "type": "STRING",
                "description": "Optional raw CSS string to inject."
            },
            "js": {
                "type": "STRING",
                "description": "Optional raw JavaScript snippet to execute."
            }
        }
    },
    "handler": web_customize
}
