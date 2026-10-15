# Zaya taskbar companion

Run `python main.py` as usual. The taskbar character loads alongside the existing
assistant, audio, WhatsApp, tools and reminders. Right-click the character to
open the combined Settings & Controls window. The previous dashboard/head
interface is no longer displayed. Closing the controls window leaves the companion
running; choose **Exit Zaya** from the tray icon to quit the application.
First-time API setup opens in the controls window. Media opens in its own
resizable display, with sound on and the microphone active. Media playback
never automatically mutes the microphone. Closing playback stops both video
and its soundtrack. Camera, results and conversation history use their own
windows when requested.

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
preloaded local WAV with its own bubble text. All poke reactions use the same
picture from `assets.poked`, normally `assets/poked.png`. Playback is local and instant: no
Gemini request, internet connection, or live AI session is required. A cooldown
avoids repeated interruptions. Microphone mute does not mute these local clips.
Set `poke_audio_enabled` to `false` to disable poke sound separately. If Zaya is
already speaking, the selected clip waits until that speech finishes rather than
being silently discarded. Microphone echo is suppressed during local playback.

The supplied Nika clips use these lines with the shared poked picture:

| Saved voice | Bubble text |
| --- | --- |
| `assets/poke/ouch.wav` | Ouch! Stop poking me! |
| `assets/poke/gentle.wav` | Be gentle with me! |
| `assets/poke/hurts.wav` | Hey, that hurts! |

```json
"poke_reactions": [
  {"text": "Ouch! Stop poking me!", "audio": "assets/poke/ouch.wav"},
  {"text": "Be gentle with me!", "audio": "assets/poke/gentle.wav"},
  {"text": "Hey, that hurts!", "audio": "assets/poke/hurts.wav"}
]
```

Add more entries to add more reactions. WAV audio is preloaded when the bar
starts or configuration is reloaded. A missing poked image uses the standby
fallback. Older per-reaction image fields are ignored. Missing audio never triggers an AI voice call.
The older `reaction_lines` list is retained for configuration compatibility but
does not generate speech on click.

To generate new configured audio once, use
`python -m tools.generate_poke_voices`. Existing files are kept. To regenerate
clips after editing their text, add `--overwrite`. Only this generation step
requires the configured Gemini API key and network access.

All Zaya replies also appear in a cloud-shaped bubble above the character,
including streamed speech, WhatsApp announcements and poke text. Long text is
shortened with `........`; the complete reply remains in Conversation History,
available from Settings & Controls. Raw tool logs stay in that history window.
An active task shows a `Thinking...` cloud. The bubble does not capture clicks
or keyboard focus. Configure `bubble_max_characters` (default 140),
`bubble_duration_ms` (6500), and `bubble_max_width` (300) in `zayabar.json`.

The app's existing proactive behavior and controls remain available in its
Settings & Controls window.

Set `enabled` to `false` to run with the controls window only; or set
`show_main_window_on_start` to `true` to show the controls and companion on startup.
Your optional artwork can be kept under ignored `assets/zayabar/`. Configuration
paths are local to your computer; do not stage personal path edits accidentally.

## Speech and background sound

Zaya lowers other Windows apps and her media display while you speak, while she
speaks, and during poke voices. Her voice mixer level rises to full volume;
the system master volume and mute buttons remain under your control. Previous
levels return after speech ends. Microphone mute, wake-word sleep and push-to-talk
still gate microphone detection. Detection runs locally without extra AI calls.

Optional settings in `zayabar.json` (restart Zaya after changing these):

```json
"audio_ducking": {
  "enabled": true,
  "background_ratio": 0.2,
  "voice_volume": 1.0,
  "release_seconds": 0.8
}
```

The default background level is 20% of each app's existing level. Newly opened
audio sessions are included while speech continues, and closing Zaya restores
the levels. Manual mixer changes are preserved. This controls computer audio,
not physical room noise. Speech in music or a nearby TV can trigger local voice
detection; headphones reduce that spill into the microphone. Windows per-app
mixing requires the installed `pycaw`/`comtypes` dependencies, and microphone
speech detection uses `webrtcvad-wheels`. Other platforms still duck the built-in
media display.
