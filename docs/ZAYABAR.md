# Zaya taskbar companion

Run `python main.py` as usual. The taskbar character loads alongside the existing
assistant, audio, WhatsApp, tools and reminders. Right-click the character to
open the original full Zaya window. Closing that window leaves the companion
running; choose **Exit Zaya** from the tray icon to quit the application.
First-time API setup still opens the original setup window.

Edit the root `zayabar.json` file to supply your own images. Blank paths display
a small Zaya placeholder until your artwork is ready. There is no bundled anime
character. Paths can be absolute or relative to this configuration file:

```json
"assets": {
  "standby": "C:/Pictures/Zaya/standby.gif",
  "thinking": "C:/Pictures/Zaya/thinking.png",
  "poked": "C:/Pictures/Zaya/poked.png",
  "talking": {
    "neutral": "C:/Pictures/Zaya/neutral.png",
    "happy": "C:/Pictures/Zaya/happy.png",
    "sad": "C:/Pictures/Zaya/sad.png",
    "angry": "C:/Pictures/Zaya/angry.png",
    "surprised": "C:/Pictures/Zaya/surprised.png"
  }
}
```

Replace only the `assets` object in the full file; retain its other settings.
Use forward slashes in Windows paths, or escape backslashes as `\\`.
PNG transparency is supported; GIF files play their supplied animation. Use
a leg-swing GIF for standby and static PNGs for talking expressions. Zaya does
not animate the mouth or invent leg movements from a single picture. Missing
expression paths fall back to neutral, then standby.

Use identical canvas size and pose alignment for all modes. `seat_fraction`
is the vertical seated contact point, measured from the top: `0.6` means 60%.
The character is positioned at the taskbar's top edge. By default its size is
reduced as necessary to keep hanging legs within the visible taskbar area;
adjust `width`, `height`, and `seat_fraction` for your artwork. Disable
`fit_legs_to_taskbar` to use the configured size, with the feet kept on screen.

Drag the character horizontally to move it; its position stays saved locally.
`screen_index` selects a monitor. The tray icon offers **Character configuration**
and **Reload zayabar.json** so images can be changed without restarting the AI.
Invalid configuration edits retain the currently loaded character.

Speaking and thinking states follow the existing assistant/runtime signals.
The assistant can select a response expression through `avatar_expression`.
Double-click shows the poked picture and requests a random line from
`reaction_lines`, using the Nika voice without computer tools. A cooldown avoids
repeated interruptions. Reactions stay silent while muted or while Zaya is
already speaking; provider/network access is needed for voice playback.
The app's existing proactive behavior and controls remain available in its
original window.

To restore the original startup behavior, set `enabled` to `false`; or set
`show_main_window_on_start` to `true` to display both interfaces on startup.
Your optional artwork can be kept under ignored `assets/zayabar/`. Configuration
paths are local to your computer; do not stage personal path edits accidentally.
