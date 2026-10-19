# The Zaya phone companion (Android)

The phone is a second **interface** to the Zaya that is already running on your
laptop — not a second Zaya. There is one runtime, one Gemini session, one memory,
one task list, one WhatsApp link. The phone renders what the laptop sends and
sends back what you type, say, or tap.

Nothing on the phone needs an API key, and nothing on the phone decides anything:
state, emotion, tasks, alerts and calls all originate on the laptop.

- Source: `mobile/android/` (Kotlin, Jetpack Compose, no Flutter)
- Laptop side: `dashboard/mobile_api.py`, registered onto the existing dashboard
  app by `dashboard/server.py` — no second server, no second port
- Wire contract: `core/mobile_protocol.py` (`protocol_version: 1`)

## What you need

| Requirement | Why |
| --- | --- |
| Android 8.0 (API 26) or newer | Foreground service, Keystore, notifications |
| The laptop running Zaya with the dashboard enabled | The phone talks to the same process |
| Both devices on the same Tailscale tailnet | The documented transport; the dashboard serves port 8000 and `*.ts.net` is the only cleartext-allowed host besides localhost |
| JDK 17+ and the Android SDK, only if you build the APK yourself | The repo ships sources, not a signed release APK |

The laptop's dashboard serves plain HTTP on its usual port, so the address to type
is `http://<machine>.your-tailnet.ts.net:8000`. Cleartext is allowed only for
`*.ts.net`, `localhost`, `127.0.0.1` and `::1`: a Tailscale name is safe because
the tailnet itself is WireGuard-encrypted, while any other host must be reached
over `https://`. See
`mobile/android/app/src/main/res/xml/network_security_config.xml`.

## Pairing (once per phone)

1. On the laptop, open Zaya's **Settings & Controls** and press **Remote Control**.
   The overlay shows a URL and a six-character key that expires after 600 seconds.
2. On the phone press **Zaya → Settings**.
3. Enter the laptop address exactly as the overlay shows the host part, for
   example `your-laptop.your-tailnet.ts.net:8000`.
4. Enter the six-character key and a name for the phone, then press **Pair**.

The phone keeps its device credential encrypted with the Android Keystore
(`SecretBox`, AES-GCM, key never leaves the Keystore) and stores it in DataStore,
so it reconnects after a reboot, an app restart, or a laptop restart without a new
key. Press **Forget this laptop** to remove it locally, or revoke it on the laptop
by its own action — a revoked phone is disconnected with `4001` and shows
"removed from Zaya" instead of retrying forever.

Five wrong pairing attempts from one address are locked out for a minute. Five
wrong device logins revoke nothing but are rate-limited and counted per device.

## What the phone can do

| Screen | What it shows | What it can do |
| --- | --- | --- |
| Home | Zaya's current look (state + emotion from the laptop), her caption, the connection badge, the transcript | Type a command, poke, open the call/chat |
| Chat | The same transcript the desktop keeps, with per-command status | Send text, resend an unanswered command after a reconnect |
| Tasks | The laptop's task runtime, newest first: goal, state, active step, attempts, error | Refresh; read-only by design |
| WhatsApp | Chats the laptop has observed, alert score and reason, per-chat mode, global mode | Owner mode switches only (`auto`/`observe`, per-chat observe → paused). Message text is never sent to the phone as instructions |
| Files | The laptop's uploads folder | Download to the phone, upload from the phone |
| Settings | Pairing, output routing, connection detail, background service | Switch output between desktop, phone and both; mute; disconnect |

Commands typed on the phone go through the same approval path as commands typed on
the desktop: the laptop starts a **fresh owner goal and scope per command**, tagged
`TRUST_AUTHENTICATED_REMOTE_OWNER`. The phone cannot smuggle in a command through a
WhatsApp message, a file name, or a web page — those paths never reach the command
queue, which is covered by tests.

## Voice and calls

Voice is raw PCM16 over two separate sockets, because they fail differently:

| Socket | Direction | Format |
| --- | --- | --- |
| `/ws/mobile` | JSON events both ways, plus your microphone | 16 kHz mono PCM16, frames ≤ 32 KB |
| `/ws/phone-output` | Zaya's voice to the phone speaker | 24 kHz mono PCM16 |

The microphone opens only during a call you answered, uses the
`VOICE_COMMUNICATION` source with echo cancellation and noise suppression, and
closes the moment the call ends — the phone never pushes room noise into a live
session. Both directions are bounded byte queues: the phone drops the *oldest*
audio when it falls behind (about two seconds of Zaya's voice), and the laptop
keeps a five-second bounded queue per listener, so a slow phone can never stall
the desktop's own audio.

Calls are started by the laptop, never by the phone:

| Priority | Name | On the phone |
| --- | --- | --- |
| P0 | critical | Full-screen incoming call, ringtone, answer/decline |
| P1 | immediate | Full-screen incoming call, ringtone, answer/decline |
| P2 | important | A notification only — never takes over the screen |
| P3 | normal | A notification, silent (`quiet`) |

A missed call produces **one** summary notification (channel: *Missed Zaya calls*)
with what the call was about, and it never repeats itself. While a call is active,
Zaya's voice is routed to the phone automatically; when it ends, the previous
route is restored. Output routing never changes from the phone on its own.

## Files

A phone uploads and downloads with the device credential, not the dashboard's
owner token:

- `GET /api/mobile/files` — the uploads folder, newest first
- `GET /api/mobile/download?name=…` — streams one file (name-only, never a path)
- `POST /api/mobile/upload` — multipart `file`, same folder, same naming rules and
  500 MB limit as the dashboard's own `/api/upload`; a name collision becomes
  `name_1.ext` instead of overwriting, and the desktop's transfer list is told
  about it

Uploaded files land in the same folder the runtime already uses, so Zaya can act
on them immediately ("summarise the file I just sent").

## The laptop's side of the contract

Everything the phone sees arrives as one envelope,
`{protocol_version, type, timestamp, payload}`, produced by
`core/mobile_bridge.py` from the existing event bus. Unknown types are ignored by
the phone, which is what lets the laptop add events without shipping a new APK.

| Emitter | Goes to the phone as |
| --- | --- |
| `zaya.state.changed` + `avatar.emotion` | `zaya.state` (state + emotion, the only authority) |
| captions / speech | `zaya.caption` |
| chat transcript | `chat.message` |
| `core/remote_commands.py` | `command.status` (submitted → acknowledged → executing → completed/failed) |
| task runtime | `task.created` / `task.updated` / `task.completed` / `task.failed` / `task.cancelled` |
| WhatsApp observer | `whatsapp.message.received`, `whatsapp.alert.created`, `whatsapp.mode` |
| policy warnings | `system.warning`, `system.notify`, `notification` |
| `core/mobile_calls.py` | `call.incoming`, `call.answered`, `call.ended`, `call.missed` |
| Zaya's audio | raw PCM frames on `/ws/phone-output` |

Two behaviours are deliberate and worth knowing when reading the logs:

- The phone's own command is echoed back on `chat.message`; the phone folds the
  echo into the line it already drew (request-id match) instead of showing two.
- Stream failures are independent: a wedged audio socket, a rejected event, a
  dropped frame and a dead control socket each fail alone. A phone that stops
  reading cannot interrupt the desktop's audio loop, and a control reconnect does
  not interrupt a live call.

## Building the APK

The Gradle wrapper is committed, so no local Gradle install is needed:

```powershell
cd mobile\android
.\gradlew.bat :app:assembleDebug
```

The APK lands in `mobile/android/app/build/outputs/apk/debug/app-debug.apk`.
Install it with `adb install -r app-debug.apk` (or copy it to the phone).

| Piece | Version |
| --- | --- |
| Gradle / Android Gradle Plugin | 9.3.1 / 8.13.1 |
| Kotlin / Compose BOM | 2.2.21 / 2025.12.00 |
| compileSdk / targetSdk / minSdk | 36 / 36 / 26 |
| JVM target | 17 (JDK 21 builds it fine) |

`mobile/android/image.txt` is the owner's checklist for artwork: drop
`zaya_neutral.png`, `zaya_happy.png`, `zaya_angry.png`, `zaya_surprised.png`
(and optionally `zaya_sad.png`, `zaya_thinking.png`, `zaya_standby.png`,
`zaya_poked.png`, `zaya_background.png`) into `mobile/android/assets/`. They are
crops of the existing desktop art — chest-up, same framing for every emotion. A
missing file falls back to `zaya_neutral.png`, then to the bundled crop of the
desktop set, so the app never shows a blank face and never invents its own art.
The launcher icon is derived from the same assets by
`tools/make_android_assets.py`.

## Tests

```powershell
# phone-side logic (protocol, dedupe, backoff, audio budget, event → screen)
cd mobile\android
.\gradlew.bat :app:testDebugUnitTest

# laptop side, from the repository root
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

The JVM suite is deliberately Android-free: `ZayaModel` is the single place where
laptop events become screen state, so "the phone never decides anything" is
checkable without a device or an emulator.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Settings says "not paired" after a reboot | Expected until you pair once; after pairing the credential is in the Keystore and survives restarts. |
| "Zaya is unreachable — retrying" | The laptop's dashboard must be running and both devices on the tailnet. Retry pacing is exponential (1 s → 30 s) with jitter, so a short outage heals by itself. |
| Pairing fails with 401 | The key expires after ten minutes and works exactly once — press **Remote Control** again. |
| Connected but silent on a call | Check the phone's media volume and that the call is *answered* (the microphone only opens then). Output routing is on the Settings screen. |
| Zaya's voice comes from the laptop, not the phone | Output route is `desktop`; switch to `Phone` or `Both`, or answer a call (a call routes to the phone automatically). |
| A command stays "submitted" | The laptop was asleep; the phone resends in-flight commands after a reconnect and the laptop dedupes by request id, so it will not run twice. |
| "This phone was removed from Zaya" | It was revoked on the laptop; pair again with a fresh key. |
| Build fails on `compileSdk 36` | Install Android SDK Platform 36 and set `sdk.dir` in `mobile/android/local.properties`. |
