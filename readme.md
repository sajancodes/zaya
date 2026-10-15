# Zaya

**Created and developed by Sajan Rai — [sajancodes](https://github.com/sajancodes).**

Zaya is a desktop voice assistant, animated taskbar companion, and personal
computer operator. It combines Google Gemini Live conversation with real tools
for applications, browsers, files, terminal commands, Git, media, and optional
WhatsApp monitoring. Its configured voice is **Nika**.

The current development and delivery branch is **`main`**. Earlier implementation
history is also available on `zaya-updates`.

## Contents

- [Capabilities](#capabilities)
- [Requirements and installation](#requirements-and-installation)
- [Everyday controls](#everyday-controls)
- [Character artwork, voices, and bubbles](#character-artwork-voices-and-bubbles)
- [Media and audio ducking](#media-and-audio-ducking)
- [Full Access and command permissions](#full-access-and-command-permissions)
- [Browser automation and recovery](#browser-automation-and-recovery)
- [WhatsApp connection and chat modes](#whatsapp-connection-and-chat-modes)
- [Optional integrations](#optional-integrations)
- [Configuration and private data](#configuration-and-private-data)
- [Architecture](#architecture)
- [Testing and troubleshooting](#testing-and-troubleshooting)
- [Creator, credits, and license](#creator-credits-and-license)

## Capabilities

| Area | Implemented behavior |
| --- | --- |
| Voice conversation | Live microphone input, Nika speech, transcripts, audio-device selection, push-to-talk, and optional local wake-word gating. |
| Taskbar companion | PNG/GIF artwork, standby and thinking states, talking expressions, text bubbles, saved poke voices, dragging, and a right-click menu. |
| Desktop assistance | Open applications, inspect the screen or camera when requested, operate computer controls, and process supported files. |
| Development | Run actual shell commands, retain working directories, capture output and exit codes, cancel processes, inspect repositories, commit, and push with verification. |
| Browser | Open URLs normally, perform interactive automation, verify destinations, and recover from closed browser contexts. |
| Media | Play local files and supported streams in a separate window, with sound on and the microphone active. |
| Audio priority | Lower background computer audio during detected speech, prioritize Zaya's voice, and restore previous levels afterward. |
| WhatsApp | Reconnect a linked Hermes session, observe incoming messages, announce sender/context, and support per-chat observation, drafts, or assistant auto replies. |
| Task visibility | Keep durable task state, bounded retries, diagnostics, and evidence instead of assuming every tool response means success. |
| Extensions | Load action modules and optional productivity, reminder, and remote-control plugins. |

Provider APIs, external applications, authentication, and optional integrations
must be available for their features to work. Browser launch alone is reported
as unverified until Zaya observes the result.

## Requirements and installation

- **Python 3.11–3.13**; the Windows regression environment uses Python 3.13.
- Git for cloning and repository operations.
- Windows is the primary tested desktop environment. Some modules include
  macOS/Linux implementations; OS-specific tools and audio mixing vary.
- A microphone and working audio output for voice conversation.
- A configured Gemini API key, network access, and available provider quota.
- Playwright browser binaries for interactive automation.
- Optional: Hermes and its Node dependencies for WhatsApp.

The configured Live model is `models/gemini-3.8-live` in `core/gemini.py`.
Nika uses the compatible Live route; model availability depends on the account
and provider. Older Live models do not provide the same Nika support.

Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/sajancodes/zaya.git
cd zaya
py -3.13 -m venv .venv
.venv\Scripts\python.exe setup.py
.venv\Scripts\python.exe main.py
```

`setup.py` installs Python dependencies and attempts to install Playwright
Chromium and Firefox. To install those directly instead:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium firefox
```

Enter your Gemini API key in the first-run setup window. The taskbar character
starts with `main.py`; Settings & Controls opens when initial configuration is
needed. Existing local settings and linked WhatsApp credentials are retained.

Use **Create Desktop Shortcut** in Settings & Controls for convenient launches.
If you move or rename the project folder, update the shortcut's working directory
and script path. Python virtual-environment launchers may also need repair or
recreation after a move.

## Everyday controls

| Interaction | Result |
| --- | --- |
| Right-click Zaya | Menu for Settings & Controls, character configuration, reload, microphone mute, and Close Zaya. |
| Double-click Zaya | One configured poke voice and its text bubble. |
| Drag Zaya horizontally | Move her along the taskbar; position is saved locally. |
| Settings & Controls | Audio devices, command permissions, integrations, history, and existing controls. |
| Close the controls window | Keep the companion and assistant running. |
| Close Zaya | Quit, stop the live session, and restore ducked audio. |
| Launch `main.py` again | Bring forward the running Zaya instead of creating a second companion, microphone, or AI session. |

The older full dashboard/head interface is no longer the main desktop surface.
Media, camera, results, and conversation history open in separate windows.

Push-to-talk and wake-word controls remain available. An optional wake model
retains its trained legacy phrase; renaming the assistant does not retrain it.
Use ordinary listening, push-to-talk, or the wake button as configured.

## Character artwork, voices, and bubbles

Edit **`zayabar.json`** in the project root. Image paths can be relative to that
file or absolute. PNGs provide static expressions; GIFs provide animation such
as moving legs during standby.

```json
{
  "assets": {
    "standby": "assets/standby.gif",
    "thinking": "assets/thinking.png",
    "poked": "assets/poked.png",
    "talking": {
      "neutral": "assets/neutral.png",
      "happy": "assets/happy.png",
      "sad": "assets/sad.png",
      "angry": "assets/angry.png",
      "surprised": "assets/surprised.png"
    }
  }
}
```

This is an excerpt: keep the other settings in your existing file. Use
**Reload zayabar.json** after changing artwork. Missing expressions fall back
to available neutral or standby artwork. Expression cues also select configured
voice-delivery tones.

All poke reactions share `assets.poked`. Each has its own text and local WAV
file. Saved clips are preloaded and played without another AI request; a poke
during Zaya's speech waits for that speech to finish.

```json
"poke_reactions": [
  {"text": "Ouch! Stop poking me!", "audio": "assets/poke/ouch.wav"},
  {"text": "Be gentle with me!", "audio": "assets/poke/gentle.wav"},
  {"text": "Hey, that hurts!", "audio": "assets/poke/hurts.wav"}
]
```

To generate configured Nika clips once:

```powershell
.venv\Scripts\python.exe -m tools.generate_poke_voices
```

Existing clips are kept unless `--overwrite` is provided. Generation requires
provider access; subsequent local playback does not. Microphone mute and poke
sound are separate settings (`poke_audio_enabled`).

Replies appear in a cloud-shaped bubble. The default limit is 140 characters;
longer text ends with `........`. Complete replies remain in Conversation
History. See [the companion configuration guide](docs/ZAYABAR.md) for size,
position, timing, expressions, and fallback behavior.

## Media and audio ducking

Media opens in a separate resizable display with sound on. Opening or muting
media does not automatically mute the microphone. Closing playback stops both
the video and a separate soundtrack.

During your speech or Zaya's speech, background computer audio drops to 20% of
its previous level by default. Zaya's voice receives mixer priority; previous
levels return afterward. Poke voices participate too. Windows uses per-session
audio control, while Zaya's own media outputs are adjusted separately.

```json
"audio_ducking": {
  "enabled": true,
  "background_ratio": 0.2,
  "voice_volume": 1.0,
  "release_seconds": 0.8
}
```

Restart after changing audio-ducking settings. Speech detection runs locally
using WebRTC VAD and respects microphone mute, wake-word sleep, and push-to-talk.
This controls computer audio rather than physical room noise. Speech leaking
from songs or a nearby TV can trigger detection.

## Full Access and command permissions

**Settings & Controls → Full Access** controls automatic owner execution.

- **Off:** ordinary operations run directly; sensitive or opaque shell commands
  and irreversible actions request the on-screen confirmation.
- **On:** owner-requested commands and actions run without Zaya's confirmation
  step, using the existing Windows account's permissions.

Fresh configurations default to off. The owner's choice is saved locally and
can be changed at any time. Full Access does not bypass Windows UAC or grant
another account's privileges. It is an approval setting, not an OS sandbox.

External messages, web content, and tool output do not acquire privileged
execution context or enable this setting. Commands retain timeouts, cancellation,
bounded output, exit codes, and task evidence. Successful side effects are not
blindly repeated; safe recoverable failures have a bounded retry policy.

## Browser automation and recovery

Simple open/search requests can launch your normal browser with its existing
profile. Interactive actions use Playwright. For verified navigation, Zaya
compares the observed URL with the requested destination; a redirect to login
is not proof that the intended page opened.

When an automation window closes, Zaya invalidates the cached context and can
relaunch it on the next request. Surviving tabs are reused, simultaneous page
requests share one launch, and recovery is bounded. Clicks, typing, and form
submissions are not replayed. Failures record exception evidence instead of
appearing only as a generic `partial` result.

A busy or locked regular browser profile can require Zaya's separate persistent
automation profile. That profile keeps its own sign-ins. Compatibility profile
paths may still contain older internal names.

## WhatsApp connection and chat modes

1. Open **Settings & Controls → WhatsApp Connection**.
2. Ensure Hermes and its bridge dependencies are installed.
3. Display the real connection QR and scan it from your phone's WhatsApp
   **Linked devices → Link a device** screen.
4. Check connection status before asking Zaya to send or handle messages.

Zaya saves a pointer to the exact Hermes linked-device session and reconnects
it on later launches. Pairing keys remain in Hermes's own profile. Incoming
messages are stored locally with IDs, direction, and contact identity.
Announcements describe newly observed messages and wait for a quiet interval.

| Chat mode | Behavior |
| --- | --- |
| Observation/monitoring | Announce and inspect observed messages; do not automatically send replies. |
| Draft | Prepare replies for owner review. |
| Auto | Handle an explicitly enabled chat as Zaya; uncertain or important replies can be held for review. |

Manual owner replies pause automatic handling. Use `stop_auto` to return a chat
to observation and `mute_alerts` to silence its announcements. Replies identify
Zaya as the assistant instead of pretending to be you.

When another Hermes gateway owns the connection, Zaya uses the observation hook
instead of competing for its queue or linked-device session. Hook data can be
incomplete and cannot authorize automatic replies. Status reports the actual
transport and feed capability. Unread counts refer to locally observed messages;
full history and recipient read receipts are not guaranteed.

Optional hook/project setup:

```powershell
.venv\Scripts\python.exe -m tools.zaya_setup --install-hermes-hook --project .
```

Restart an independently managed Hermes gateway when needed to load its hook.
Pairing credentials are separate from browser automation state.

## Optional integrations

Settings & Controls exposes remote control, plugin settings, memory, audio
devices, and diagnostics. The authenticated phone dashboard can relay supported
commands and files. Phone microphone support also depends on the browser's
permissions and secure-context requirements.

Plugins add productivity and service integrations. Services such as Telegram
require their own credentials; missing optional tokens are reported separately
from voice readiness. Duplicate tool names are rejected and shown in diagnostics
rather than silently replacing a core action.

## Configuration and private data

| Location | Purpose |
| --- | --- |
| `zayabar.json` | Character paths, poke clips, expressions, bubbles, and ducking. |
| `config/api_keys.json` | Local API key, voice/device preferences, Full Access, and service settings; ignored by Git. |
| `memory/` | Local profile, project aliases, task and observed WhatsApp state. Private runtime files are ignored. |
| `logs/runtime/events.jsonl` | Structured tool results and redacted evidence; ignored by Git. |
| Hermes profile | Linked-device credentials outside source control. |
| `assets/zayabar/` | Ignored location for optional personal artwork. |

The root character configuration and bundled assets are versioned. Keep private
paths and additional personal artwork local when editing them. Profile imports
are explicit; source code does not seed sensitive historical facts.

## Architecture

```text
main.py                  Live session, microphone, speaker, tools and lifecycle
ui.py                    Settings & Controls and desktop window integration
actions/                 Desktop, browser, shell, Git and media tools
core/                    Policy, task runtime, audit, events and audio
services/zayabar.py       Taskbar character, expressions and poke playback
services/whatsapp/       Pairing, identity, transport, inbox and chat policy
memory/                  Configuration helpers and private state interfaces
dashboard/               Optional phone dashboard
tests/                   Offline regression and integration tests
tools/                   Setup helpers and poke-voice generation
docs/                    Character, implementation and validation documentation
```

Internal names such as `JarvisLive`, `JarvisUI`, legacy profile folders, and
startup keys remain where changing them would break compatibility. The visible
assistant identity is Zaya, created by Sajan Rai.

## Testing and troubleshooting

Run checks with the same interpreter used to launch Zaya:

```powershell
.venv\Scripts\python.exe -m pip install ruff
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m ruff check --isolated --select E9,F63,F7,F82 core actions services memory main.py ui.py tests tools
```

The suite covers temporary repositories/processes, browser recovery against
local HTTP pages, Qt UI integration, audio restoration, command permissions,
and simulated WhatsApp events. It does not send live WhatsApp messages. GitHub
Actions runs Windows checks on pushes to `main` and `zaya-updates`; local test
success and hosted CI status are reported separately.

| Symptom | Check |
| --- | --- |
| `Target page, context or browser has been closed` | Restart into the updated code; closed-window recovery is included. Inspect error evidence if a fresh launch fails. |
| Browser executable missing | Run `python -m playwright install chromium firefox` with Zaya's interpreter. |
| Browser opens but navigation is not verified | Inspect the actual URL, login redirect, profile, and returned evidence. |
| Poke text appears without sound | Check `poke_audio_enabled`, the WAV path, and output device; reload the character configuration. |
| Background audio stays quiet | Let speech end or close Zaya normally; check for nearby speech reaching the microphone. |
| Administrator operation fails | Full Access uses current account privileges; Windows may still require elevation. |
| No WhatsApp announcements | Check connection, complete live feed, mute-alert settings, and whether speech is busy. |
| Telegram reports no token | Configure that optional integration or leave it unused; it does not establish WhatsApp readiness. |
| Second launch shows the controls | The single-instance guard is activating the running Zaya. |
| Hosted checks do not start | Inspect the Actions annotation; billing/spending limits are separate from test failures. |

See [validation and rollback notes](docs/VALIDATION.md),
[implementation documentation](docs/implementation.md), and the
[implementation plan](docs/ZAYA_IMPLEMENTATION_PLAN.md). Before reverting a
feature, inspect dependent commits and preserve private configuration, memory,
and linked-device credentials.

## Creator, credits, and license

**Zaya is created and developed by Sajan Rai.** Source and ongoing development
are maintained under [sajancodes/zaya](https://github.com/sajancodes/zaya).

The project builds on **Mark LV by FatihMakes**. Original attribution and the
**CC BY-NC 4.0** license remain in [LICENSE](LICENSE). Gemini, Qt, Playwright,
Hermes, and other dependencies retain their respective credits and terms.
See [CREDITS.md](CREDITS.md) for the project attribution.
