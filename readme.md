# Zaya

**Built by Sajan Rai.** A desktop voice assistant and evidence-driven personal
computer operator, using Google Gemini Live with the **Nika** voice.

Zaya can talk, inspect the screen, operate applications and browsers, manage
files, run terminal commands, and work with Git repositories. It records task
state and verifies critical outcomes before reporting success.

## Start

Use Python 3.11–3.13:

```powershell
python setup.py
python main.py
```

Enter your Gemini API key in the setup screen. Existing settings are preserved.
Nika uses Gemini 3.8 Live; older Live models do not support this voice. API access,
network connectivity and provider quota are required. Optional legacy wake-word
models retain their trained phrase; changing the assistant name does not retrain
speech detection. Push-to-talk and the wake button remain available.

## Operator capabilities

| Tool | Behavior |
| --- | --- |
| `terminal_exec` | Real PowerShell/CMD or Unix shell execution, explicit working directory, bounded output, exit codes, timeout and cancellation. |
| `git_control` | Inspect status and diffs, stage explicit files, create commits, use branches, fetch, fast-forward pull, push and compare remote/local SHAs. |
| `browser_control` | Known-site aliases and exact navigation verification with `verify=true`. Browser launches without observation remain unverified. |
| `runtime_status` | Read current, waiting, failed and recent tasks from persistent local state. |
| `system_diagnostics` | Inspect exact action/plugin failures, provider configuration, audio, browser and integration availability. |
| `whatsapp` | Pair, reconnect, read observed inbox state, send through the Hermes transport, manage chat modes, mute or acknowledge alerts. |
| `personal_profile` | Explicit private profile import and local project aliases. |

Existing avatar, voice, screen/camera, file, browser, reminder, video and plugin
systems remain. Internal compatibility names and startup registration keys are
retained where migration would break existing installations.

A successful side effect is not automatically repeated. Retries require evidence
of a safe recoverable failure and have a three-attempt limit. Destructive or
opaque shell commands require a real HUD confirmation. This confirmation policy
is for owner-authorized execution; it is not an operating-system sandbox.

## Taskbar character

Running `main.py` also starts a transparent taskbar companion. Set your PNG/GIF
paths in `zayabar.json`; right-click the character to open combined Settings &
Controls. Media uses its own resizable window with sound on and the microphone
active. Standby GIFs, thinking pictures, response expressions and double-click
Nika reactions are supported. Until images are supplied, a small placeholder
appears. See [character configuration](docs/ZAYABAR.md) for paths and controls.

## WhatsApp

Open **Setup → WhatsApp Connection**, then scan the real QR using your phone's
**WhatsApp → Settings → Linked devices → Link a device**. The panel saves a pointer
to the exact Hermes linked-device session and reconnects it on later launches.
Zaya never copies linked-device keys into its repository or model context.

When Zaya owns the Hermes local bridge, it receives complete live message IDs and
direct-chat owner outgoing events. Phone and linked IDs share one conversation
when the feed establishes their relationship; owner-sent messages never label
the recipient with the owner's name. Explicit contact corrections are saved
locally with `identify_contact`.

Chats start in observation mode. Incoming messages queue spoken sender/context
notifications, including ordinary greetings. Notifications use a separate Nika
session with no tools, wait while you are speaking, and support `mute_alerts`.
Use `monitor` to observe without replying and `stop_auto` to return to observation.
WhatsApp monitoring runs in the background without an open chat window.
Explicitly choose draft/auto mode for a particular chat; important or uncertain replies are
held for owner review. Manual owner replies pause automatic handling. Ordinary
contact text cannot reach terminal, filesystem, Git or other privileged tools.
Automatic replies identify Zaya as the assistant rather than impersonating you.

If an independently running Hermes gateway owns the connection, Zaya uses the
observation hook rather than polling its consuming queue or starting another
session. Hook text is incomplete and cannot authorize auto replies. A recorded
chat mode alone is not proof of an active complete feed. `whatsapp status` reports
these distinctions. Historical inbox contents and recipient read receipts are
not guaranteed; unread counts refer to locally observed messages.

Hermes must already be installed. Its bridge needs Node and its own dependencies.
To install the optional observation hook:

```powershell
python -m tools.zaya_setup --install-hermes-hook --project .
```

This preserves pairing. Restart a separately managed Hermes gateway when convenient
so it loads the hook. Do not run a second bridge using the same paired session.

## Private data

API keys, profile imports, project aliases, runtime databases, chats, audit logs,
screenshots, QR codes and linked-device credentials stay local and are ignored
by Git. Profile import is explicit; source code does not seed sensitive historical
facts. Configuration is under `config/`, personal memory under `memory/`, and the
Hermes session remains in its own profile directory.

## Test and rollback

```powershell
python -m playwright install chromium
python -m unittest discover -s tests -v
```

Offline tests use temporary repositories and processes, an isolated browser,
simulated Hermes events and a real UI smoke test. They do not send WhatsApp
messages. GitHub Actions runs the Windows regression suite on pushes.

See [validation and rollback notes](docs/VALIDATION.md) and the
[implementation contract](docs/ZAYA_IMPLEMENTATION_PLAN.md). Implementation phases
are separate commits on `zaya-updates`; revert dependent commits deliberately,
and preserve local configuration and paired sessions.

## Attribution

Zaya builds on Mark LV by FatihMakes. Original attribution and the **CC BY-NC 4.0**
license are preserved in [LICENSE](LICENSE). Gemini, Qt, Hermes and other libraries
are dependencies; the active assistant identity is Zaya.
