"""Widget Forge & Live UI Generation.
Created and developed by Sajan Rai for Zaya.
Spawn live, floating desktop widgets like timers, clocks, calculators, or custom tools.
Generates standalone, reactive HTML/CSS/JS widgets with modern dark-mode aesthetic.
"""
from __future__ import annotations

import json
import re
import sys
import webbrowser
from pathlib import Path
from typing import Optional

from core.execution_policy import require_owner


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_widgets_dir() -> Path:
    out = get_base_dir() / "dashboard" / "widgets"
    out.mkdir(parents=True, exist_ok=True)
    return out


WIDGET_TEMPLATES = {
    "timer": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Zaya Mini Timer</title>
<style>
  body { margin:0; background:#0B0F19; color:#00FF66; font-family:'Courier New', monospace; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; }
  .display { font-size:48px; font-weight:bold; text-shadow:0 0 10px #00FF66; margin-bottom:20px; }
  .controls button { background:#1E293B; color:#00FF66; border:1px solid #00FF66; padding:10px 18px; margin:0 5px; font-size:16px; cursor:pointer; border-radius:4px; }
  .controls button:hover { background:#00FF66; color:#0B0F19; }
</style>
</head>
<body>
<div class="display" id="time">00:00:00</div>
<div class="controls">
  <button onclick="start()">Start</button>
  <button onclick="pause()">Pause</button>
  <button onclick="reset()">Reset</button>
</div>
<script>
  let seconds = 0, timer = null;
  function update() {
    let hrs = String(Math.floor(seconds/3600)).padStart(2,'0');
    let mins = String(Math.floor((seconds%3600)/60)).padStart(2,'0');
    let secs = String(seconds%60).padStart(2,'0');
    document.getElementById('time').innerText = `${hrs}:${mins}:${secs}`;
  }
  function start() { if(!timer) timer = setInterval(()=>{ seconds++; update(); }, 1000); }
  function pause() { clearInterval(timer); timer = null; }
  function reset() { pause(); seconds = 0; update(); }
</script>
</body>
</html>""",

    "calculator": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Zaya Ghost Calculator</title>
<style>
  body { margin:0; background:#0B0F19; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; }
  .calc { background:#1E293B; padding:20px; border-radius:12px; border:1px solid #38BDF8; box-shadow:0 0 20px rgba(56,189,248,0.2); }
  #screen { width:100%; height:45px; background:#0B0F19; color:#38BDF8; font-size:24px; text-align:right; padding:5px 10px; box-sizing:border-box; border:1px solid #38BDF8; margin-bottom:15px; border-radius:6px; }
  .grid { display:grid; grid-template-columns:repeat(4, 50px); gap:10px; }
  button { height:45px; background:#334155; color:#F8FAFC; border:none; border-radius:6px; font-size:18px; cursor:pointer; }
  button:hover { background:#38BDF8; color:#0B0F19; }
  button.op { background:#0284C7; }
</style>
</head>
<body>
<div class="calc">
  <input type="text" id="screen" readonly value="0">
  <div class="grid">
    <button onclick="clearScr()">C</button>
    <button onclick="press('/')" class="op">/</button>
    <button onclick="press('*')" class="op">*</button>
    <button onclick="press('-')" class="op">-</button>
    <button onclick="press('7')">7</button>
    <button onclick="press('8')">8</button>
    <button onclick="press('9')">9</button>
    <button onclick="press('+')" class="op">+</button>
    <button onclick="press('4')">4</button>
    <button onclick="press('5')">5</button>
    <button onclick="press('6')">6</button>
    <button onclick="calc()" class="op">=</button>
    <button onclick="press('1')">1</button>
    <button onclick="press('2')">2</button>
    <button onclick="press('3')">3</button>
    <button onclick="press('0')">0</button>
  </div>
</div>
<script>
  let s = document.getElementById('screen');
  function press(v) { if(s.value === '0') s.value = ''; s.value += v; }
  function clearScr() { s.value = '0'; }
  function calc() { try { s.value = eval(s.value); } catch(e) { s.value = 'Error'; } }
</script>
</body>
</html>""",

    "clock": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Zaya World Clock</title>
<style>
  body { margin:0; background:#0F172A; color:#E2E8F0; font-family:'Segoe UI', sans-serif; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; }
  .time { font-size:56px; font-weight:700; color:#38BDF8; letter-spacing:2px; }
  .date { font-size:18px; color:#94A3B8; margin-top:8px; }
</style>
</head>
<body>
<div class="time" id="clock">00:00:00</div>
<div class="date" id="date">Loading...</div>
<script>
  function tick() {
    let d = new Date();
    document.getElementById('clock').innerText = d.toLocaleTimeString();
    document.getElementById('date').innerText = d.toLocaleDateString(undefined, { weekday:'long', year:'numeric', month:'long', day:'numeric' });
  }
  setInterval(tick, 1000);
  tick();
</script>
</body>
</html>"""
}


def forge_live_widget(widget_type: str, custom_html: Optional[str] = None, out_dir: Optional[Path] = None) -> str:
    """Creates a standalone HTML widget file."""
    w_type = widget_type.lower().strip()
    html = custom_html if custom_html else WIDGET_TEMPLATES.get(w_type, WIDGET_TEMPLATES["timer"])

    target_dir = out_dir if out_dir else _get_widgets_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", w_type)[:25]
    out_path = target_dir / f"{slug}_widget.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)


def widget_forge(parameters: dict, **_kwargs) -> str:
    """Widget Forge Action handler."""
    require_owner()
    w_type = str(parameters.get("widget_type", "timer")).lower().strip()
    custom_html = parameters.get("html")
    auto_open = bool(parameters.get("auto_open", False))

    path = forge_live_widget(w_type, custom_html=custom_html)
    if auto_open:
        try:
            # as_uri() produces a proper file:///C:/... URI. The old
            # "file://" + os.path.abspath() form left Windows backslashes in
            # the URL ("file://C:\Users\..."), which browsers refuse to open.
            webbrowser.open(Path(path).resolve().as_uri())
        except Exception as e:
            return json.dumps({
                "status": "partial",
                "widget_type": w_type,
                "widget_path": path,
                "message": f"Widget was created at {path}, but it could not be opened automatically: {e}"
            }, indent=2)

    return json.dumps({
        "status": "success",
        "widget_type": w_type,
        "widget_path": path,
        "message": f"Spawned live desktop widget ({w_type}) at {path}"
    }, indent=2)


TOOL = {
    "name": "widget_forge",
    "description": "Interactive UI Generation & Widget Forge: Spawns live, reactive desktop widgets (timers, calculators, world clocks, custom HTML tools) rendered with modern dark-mode aesthetics.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "widget_type": {
                "type": "STRING",
                "enum": ["timer", "calculator", "clock", "custom"],
                "description": "The type of widget to forge."
            },
            "html": {
                "type": "STRING",
                "description": "Optional custom HTML/CSS/JS snippet for custom widgets."
            },
            "auto_open": {
                "type": "BOOLEAN",
                "description": "Whether to automatically open the forged widget in browser."
            }
        },
        "required": ["widget_type"]
    },
    "handler": widget_forge
}
