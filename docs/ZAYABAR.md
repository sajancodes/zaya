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
The assistant selects a response emotion through `avatar_expression`. The same
selection drives both the talking picture and the Nika delivery instruction:

| Emotion | Face path | Voice style |
| --- | --- | --- |
| neutral | `assets.talking.neutral` | Warm, calm conversation |
| happy | `assets.talking.happy` | Cheerful, smiling, energetic |
| sad | `assets.talking.sad` | Soft, caring, empathetic |
| angry | `assets.talking.angry` | Playfully annoyed or calmly firm |
| surprised | `assets.talking.surprised` | Brighter pitch and brief surprise |

Customize the style descriptions in `emotion_tones` in `zayabar.json`. These
are spoken-delivery instructions to Gemini Live, rather than fixed DSP pitch
settings. Nika stays the voice identity. Restart Zaya after changing voice-style
instructions, so its Live session picks them up. Expressions remain static
pictures. Zaya's conversational personality is warm and expressive; it avoids
routine detached disclaimers while retaining truthful capability reporting.
Double-click randomly selects a `poke_reactions` entry. Each entry pairs a
preloaded local WAV with its own picture. Playback is local and instant: no
Gemini request, internet connection, or live AI session is required. A cooldown
avoids repeated interruptions. Reactions stay silent while muted or while Zaya
is already speaking, and microphone echo is suppressed during local playback.

The supplied Nika clips are paired as follows. Generate your corresponding
images at these paths, or replace each `image` path with your exact filename:

| Picture | Saved voice | Line |
| --- | --- | --- |
| `assets/poke/ouch.png` | `assets/poke/ouch.wav` | Ouch! Stop poking me! |
| `assets/poke/gentle.png` | `assets/poke/gentle.wav` | Be gentle with me! |
| `assets/poke/hurts.png` | `assets/poke/hurts.wav` | Hey, that hurts! |

```json
"poke_reactions": [
  {"text": "Ouch! Stop poking me!", "image": "assets/poke/ouch.png", "audio": "assets/poke/ouch.wav"},
  {"text": "Be gentle with me!", "image": "assets/poke/gentle.png", "audio": "assets/poke/gentle.wav"},
  {"text": "Hey, that hurts!", "image": "assets/poke/hurts.png", "audio": "assets/poke/hurts.wav"}
]
```

Add more entries to add more reactions. WAV audio is preloaded when the bar
starts or configuration is reloaded. Missing reaction images use the normal
poked/standby fallback. Missing audio never triggers an AI voice call.
The older `reaction_lines` list is retained for configuration compatibility but
does not generate speech on click.

To generate new configured audio once, use
`python -m tools.generate_poke_voices`. Existing files are kept. To regenerate
clips after editing their text, add `--overwrite`. Only this generation step
requires the configured Gemini API key and network access.
The app's existing proactive behavior and controls remain available in its
original window.

To restore the original startup behavior, set `enabled` to `false`; or set
`show_main_window_on_start` to `true` to display both interfaces on startup.
Your optional artwork can be kept under ignored `assets/zayabar/`. Configuration
paths are local to your computer; do not stage personal path edits accidentally.
