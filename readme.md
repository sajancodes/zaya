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
- [Multiple Gemini keys and rate limits](#multiple-gemini-keys-and-rate-limits)
- [Everyday controls](#everyday-controls)
- [Character artwork, voices, and bubbles](#character-artwork-voices-and-bubbles)
- [Media and audio ducking](#media-and-audio-ducking)
- [Continue the same chat after closing Zaya](#continue-the-same-chat-after-closing-zaya)
- [Full Access and command permissions](#full-access-and-command-permissions)
- [Browser automation and recovery](#browser-automation-and-recovery)
- [WhatsApp connection and chat modes](#whatsapp-connection-and-chat-modes)
- [The Zaya phone companion (Android)](#the-zaya-phone-companion-android)
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
| Memory & recall | Archive every conversation locally; recall at most five messages on demand; semantic long-term memory; no preload on fresh startup. |
| Proactive assistance | Morning/evening briefings, contextual check-ins, anomaly alerts, commitment tracking, and quiet-hour respect. |
| Task visibility | Keep durable task state, bounded retries, diagnostics, and evidence instead of assuming every tool response means success. |
| Extensions | Load action modules and optional productivity, reminder, and remote-control plugins. |
| Phone companion | A native Android app (`mobile/android/`) mirrors Zaya's state, transcript, tasks, WhatsApp views and files, and carries two-way voice and Zaya-initiated calls over the same runtime. |
| Phone calls | Zaya rings the phone for urgent messages, owner-requested decisions, failed tasks, and finished work while the owner is away; missed calls leave one summary. |
| Phone video | Opt-in camera sharing during an answered call; the laptop receives frames and can use them as live visual context. |
| Native call controls | Answer, decline, and mute directly from the phone's incoming-call notification. |

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

## Multiple Gemini keys and rate limits

Right-click Zaya → **Gemini API keys…**. Enter one key or a comma-separated list:

```text
key_one, key_two, key_three
```

The field stays masked. Saving preserves voice, WhatsApp and other preferences,
then reconnects while preserving local History. On a `429` rate-limit response, Zaya tries
the next available configured key. Provider retry delays are respected; when
all keys are cooling down, Zaya waits and shows the reason. Helper generations
also use key failover. Credentials remain in ignored local configuration.
Direct edits to `config/api_keys.json` are read when a key is selected: use
`gemini_api_key` with comma-separated values, or `gemini_api_keys` with a list.
If both exist, the plural list takes precedence. An already connected voice
session keeps its current key until it needs a new connection.

Google applies quota per project, so multiple keys from one project can share
the same limit. Failover provides access to already available quota; it does
not guarantee that rate limits disappear. See [Google's rate-limit guide](https://ai.google.dev/gemini-api/docs/rate-limits).

Connection setup has a 20-second deadline. A slow or unavailable provider shows
connection/retry status rather than leaving a permanent Thinking state. Startup
worker failures are visible and recorded in `logs/startup_failure.log`.

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

You can interrupt Zaya while she speaks. A local echo filter checks sustained
owner speech and retains its opening audio before stopping the queued reply.
Listening resumes when playback drains, even if a tool or server turn is still
open. Speaker volume and room acoustics affect echo separation; microphone mute,
push-to-talk, and wake-word sleep still apply.

Direct listening is the default. Optional `proactive_audio: true` lets the
provider decide to ignore speech; enable it only if you want selective replies.
For a missed reply, audio diagnostics include `logs/runtime/voice_status.json`:
microphone, queue, network-send and transcription counters plus the current
gate. This local file contains no recording or transcript.

Your active request takes priority over spoken WhatsApp announcements. Incoming
messages remain queued until your request and reply finish; speaking during a
local announcement stops it and returns the speaker to your conversation.
Local speech detection retains the start of your sentence and explicitly marks
speech start and end for Gemini. Capture stays open during silence and tools;
slow tools run separately from incoming speech and interruption handling.
When capture pauses, a short generated quiet tail finishes the open input turn
without adding a recording. A reply timeout shows a listening status in the
same session; it does not restart Zaya, discard the conversation, or replay
actions. Actual connection failures still use normal connection recovery.
An explicit request to play media in Brave opens the exact requested song in
your regular browser and closes the display player. Native launch cannot verify
that the browser actually started playback.

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

## Continue the same chat after closing Zaya

Zaya saves the continuous private conversation in `memory/conversation.db`.
Voice and dashboard text are saved as they arrive; typed messages are saved
before sending. The archive and chat ID survive restarts.

Startup opens a fresh provider session. It does **not** upload previous messages,
replay old speech bubbles, restore a saved provider checkpoint, or send the whole
conversation for an automatic summary. An existing archive skips another morning
briefing. Transient reconnects inside the same running process can still resume.

Open **Settings & Controls → Last Conversation History** to view saved messages
locally, loaded in one batch when the window is requested. The current live
conversation has its own history window. Ask **“what were we doing?”** to have
Zaya fetch **at most five messages**, with a small text budget, through the
owner-only `conversation_history` tool. Search uses the same limit. This reduces
startup context usage; it does not create extra Gemini quota. Old requests and
actions are never replayed automatically. Audio/video recordings are not archived.

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

Simple open/search/new-tab requests launch your normal browser with its existing
profile and sign-ins. Set `"preferred_browser": "brave"` in local
`config/api_keys.json` to prefer Brave; a spoken request for another browser
overrides it. Without a preference, the system default is used. A running
automation session or a request to verify the URL cannot redirect an ordinary
open request into a separate profile. `git_control open_remote` also opens the
exact repository in your regular browser.

Native launch is reported as unverified because it cannot inspect the browser's
page or login. Interactive website tasks use explicit `mode: "automation"` and
Playwright. There, Zaya compares the observed URL with the requested destination;
a redirect to login is not proof that the intended page opened.

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

Say **“WhatsApp auto”**, **“WhatsApp auto mode”**, or **“enable WhatsApp auto
replies”** to turn on quiet assistant replies for current and future direct
chats. Ordinary messages and replies stay silent. Groups and explicitly paused
chats are excluded. No old messages are automatically answered. Say **“stop
WhatsApp auto”** to return direct chats to observation and spoken notifications
for new messages. Name a contact to change only that conversation instead.

Every automatic reply is labeled **Zaya · Sajan Rai’s AI assistant**. Requests
requiring the owner's judgment remain in the inbox for review. Automatic
sending requires the complete native live feed; an offline connection is
reported as incomplete instead of claiming replies are running.

Replies use relevant **current session activity**: for example, that Sajan is
listening to Sanam or working on a project. Display playback is shared only
after the player reports it is playing and cleared when paused/stopped. Project
work and explicit owner activity summaries expire rather than becoming permanent
facts. The owner can update/clear them through `session_activity`. No full live
conversation, private profile, command arguments or file paths are supplied to
the contact reply model. Unknown details receive an honest uncertainty reply;
location and availability are never inferred.

If someone asks Zaya to **pass a message to Sajan**, or sends an **urgent** update,
the sender and message are queued durably for a spoken owner notice, even in
quiet auto mode. Zaya waits for the voice session to be free, then announces it
once. A reply may say the message is queued; that is not proof the owner heard
it. Consequential decisions, commitments and sensitive requests still wait for
the owner. Ordinary chat and generic task failures do not trigger auto-mode speech.

Generic operator-task failures appear in the activity log/runtime status;
Zaya does not speak the repeated “an operator task has failed” announcement.

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

## The Zaya phone companion (Android)

`mobile/android/` is a native Android companion — Kotlin and Jetpack Compose, no
Flutter — that talks to the Zaya already running on the laptop. It is an interface,
not a second assistant: the same runtime, Gemini session, memory, task list and
WhatsApp link answer the phone.

| On the phone | Behavior |
| --- | --- |
| Home / Chat | Zaya's state and emotion exactly as the laptop reports them, never decided locally; text commands go through the same owner-scope approval path |
| Voice and calls | Two-way PCM16 voice on its own sockets; Zaya can call the phone (P0/P1 ring the phone like a real call, P2 notifies, P3 stays silent), a task that finishes while the owner is away rings him, and a missed call leaves one summary, never a repeat |
| Video | Opt-in camera sharing during an answered call; the laptop receives frames and can use them as live visual context. |
| Output | Desktop, phone or both; a call routes her voice to the phone automatically and restores the previous route afterwards |
| Tasks | The laptop's task runtime, newest first, read-only |
| WhatsApp | Read-only views plus owner mode switches; message text is never treated as a command |
| Files | Download from and upload to the laptop's uploads folder |

Pair once with the six-character key from **Settings & Controls → Remote Control**:
the credential is Keystore-encrypted on the phone and stored as a hash on the
laptop, so both sides survive restarts. The phone holds no API keys, and a laptop
command from the phone starts a fresh owner goal and scope. Full setup, build
steps and troubleshooting: [docs/mobile.md](docs/mobile.md).

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
| `memory/conversation.db` | Private continuous chat archive, command identity and provider resume checkpoint; ignored by Git. |
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
mobile/android/          Native Android companion app
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
| Phone app cannot reach the laptop | Both devices must be on the same tailnet, the dashboard must be running (port 8000), and a pairing key works once and expires after ten minutes. See [docs/mobile.md](docs/mobile.md). |
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
