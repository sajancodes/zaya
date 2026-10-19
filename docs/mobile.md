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

The phone reaches Zaya over the tailnet, so the address is
`http://<machine>.your-tailnet.ts.net:8000`: cleartext inside the tailnet, which
is already WireGuard-encrypted. Cleartext is allowed only for `*.ts.net`,
`localhost`, `127.0.0.1` and `::1`; any other host must be reached over
`https://`. See
`mobile/android/app/src/main/res/xml/network_security_config.xml`.

### If the laptop serves HTTPS

Zaya's dashboard has its own TLS mode: on first run it generates a self-signed
certificate, then serves HTTPS on 8000 plus an alias on 8001. The app cannot trust
a self-signed certificate, so the phone needs the dashboard to speak plain HTTP
inside the tailnet. Add one line to `config/api_keys.json` and restart Zaya:

```json
"dashboard_https": false
```

Port 8000 then serves HTTP and the 8001 alias is not started; the browser
dashboard keeps working (type the scheme explicitly, e.g. `http://…:8000`, since
browsers upgrade a bare host to HTTPS). Leave the setting out — or set it to
`true` — to keep the dashboard's own TLS exactly as before.

Keeping HTTPS *and* the phone is possible only with a real certificate: run
`tailscale cert <machine>.your-tailnet.ts.net` (enable HTTPS certificates in the
Tailscale admin console first), then point Zaya's dashboard at the issued pair.
Zaya's own certificate is local, self-signed and regenerates on demand, so it can
never satisfy the app on its own.

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
| P0 | critical | Full-screen incoming call, ringing, answer/decline |
| P1 | immediate | Full-screen incoming call, ringing, answer/decline |
| P2 | important | A notification only — never takes over the screen |
| P3 | normal | A notification, silent (`quiet`) |

A ring is a real ring: the phone loops its own ringtone and repeats a vibration
for as long as the laptop says the call is ringing, the screen wakes over the
lock screen, and Answer/Decline sit on both the call screen and the notification.
The phone's ringer mode is respected — normal rings and shakes, vibrate-only
shakes, silent stays silent. Ringing stops on answer, decline, a missed call, or
a dropped connection (a 60-second cap so a lost link cannot ring forever).
On Android 14+ the *Full screen notifications* switch can be revoked for the app;
without it a call still rings but only as a heads-up notification, so Settings
shows a card with a shortcut straight to that switch.

### When Zaya rings

| Trigger | Priority |
| --- | --- |
| A critical system or security problem | P0 |
| A task is blocked waiting for your decision | P1 |
| A task failed after its retry budget, or after changing the machine | P1 |
| An urgent WhatsApp message (alert score ≥ 85) | P1 |
| An action you requested from your phone is waiting on the desktop | P1 |
| **A task finished while you are away** | P1 |
| Zaya decides she needs you (`call_owner` tool) | her choice |
| Completed work while you are at the machine, important messages | a notification |

"While you are away" normally uses desktop idle time (10 minutes by default).
Saying “I'm going out” uses the owner-only `owner_presence` tool to mark you away
immediately, for 12 hours by default. “I'm back” marks you present; `auto` restores
idle detection. Only actual completed work rings, not status queries or acceptance
of a background job. The phone must be connected.

Automatic calls keep one call at a time, a 10-minute cooldown per issue, a
150-second floor and a maximum of 6 calls an hour. An explicit “call me” or test
request uses `call_owner(requested=true)` and bypasses automatic cooldowns, even
at the desktop. It still requires a connected phone and no existing call.
Suppressed alerts remain notifications. Missed calls never redial themselves.

When you call Zaya from the phone, it shows **Ringing…** and plays ringback.
The laptop randomly waits **5–10 seconds** before answering, provided its voice
session is available. Hanging up during this interval cancels the answer.
Incoming calls show Answer and Decline; answering keeps the same screen open
with the timer, Mute, Speaker and End call. Speaker switches the phone's actual
earpiece/loudspeaker; it does not route the call through the laptop.

The phone microphone opens only after answer and stops recording when muted.
During the entire answered call, including silence and mute, laptop microphone
input is ignored. Only the answering device can send call audio or hang up.
Disconnecting that phone ends the call and restores the previous output route.

### Tuning it

All optional, in `config/api_keys.json` (the same file as `dashboard_https`):

```json
"phone_calls": {
  "call_when_task_finishes": true,
  "away_minutes": 10,
  "quiet_hours": [23, 7]
}
```

- `call_when_task_finishes` — `false` keeps finished work as the silent line it
  used to be.
- `away_minutes` — how long the desktop must be untouched before you count as out.
- `quiet_hours` — a finished task waits for morning rather than ringing (it stays
  in the activity list). `null` disables the window entirely. Urgent calls — a
  blocked task, a failure, an urgent message, anything critical — ignore this and
  ring at any hour.

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
| `core/mobile_calls.py` | `call.dialing`, `call.incoming`, `call.answered`, `call.ended`, `call.missed` |
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
| The dashboard opens in a browser but the phone says it cannot reach the laptop | Check the scheme: a self-signed HTTPS dashboard cannot be paired with. Set `"dashboard_https": false` in `config/api_keys.json`, restart Zaya, and use `http://<machine>.ts.net:8000`. |
| The address does not resolve on the phone | Tailscale must be installed, signed in to the same account and toggled on there; `*.ts.net` names resolve only inside the tailnet (MagicDNS). |
| Connected but silent on a call | Check the phone's call volume and that the call is *answered* (the microphone only opens then). Output routing is on the Settings screen. |
| Zaya's voice comes from the laptop, not the phone | Output route is `desktop`; switch to `Phone` or `Both`, or answer a call (a call routes to the phone automatically). |
| A call only arrives as a notification | Android 14+: allow *Full screen notifications* for Zaya — Settings shows a card with the shortcut. |
| A finished task did not ring | Working as designed if you were at the desktop, the phone was offline, or it fell inside `quiet_hours`. It is still in the phone's activity list; `away_minutes` and `call_when_task_finishes` in `config/api_keys.json` tune the behaviour. |
| A command stays "submitted" | The laptop was asleep; the phone resends in-flight commands after a reconnect and the laptop dedupes by request id, so it will not run twice. |
| "This phone was removed from Zaya" | It was revoked on the laptop; pair again with a fresh key. |
| Build fails on `compileSdk 36` | Install Android SDK Platform 36 and set `sdk.dir` in `mobile/android/local.properties`. |


## Ringing calls and optional video (0.3.0)

An explicit “call me” request always has ringing priority, even if the model
calls its content “important” or “normal.” Automatic updates retain their quiet
notification policy. Android uses CallStyle with Answer/Decline, a looping
ringtone and vibration. Ringing respects silent/vibrate mode and Do Not Disturb.

Install the updated APK, open Zaya → Settings and finish **Set up incoming calls**:
allow call notifications, full-screen calls, and display over other apps. Android
requires the owner to grant these special permissions. Full-screen intents wake
the lock screen; the display-over-apps permission lets Zaya open the incoming call
screen while another app is in front. Without it, Android can use a heads-up call
notification. These permissions cannot be silently enabled on a real phone.

During a connected call, tap **Video** and grant camera permission. Zaya receives
bounded live JPEG samples at about one frame per second, using the front camera
when available. The preview shows what is being sent. Tap **Video off** to stop.
Camera capture also stops on hang-up, disconnect, minimizing, or leaving the call
screen. Frames remain in memory, are never recorded to disk, and only the answering
device may supply them. Laptop microphone input remains blocked throughout the
call. Zaya continues to use her existing avatar and voice; this does not fabricate
a remote human video feed.

Validation for 0.3.0: 369 desktop tests completed (six skipped); 52 Android unit
tests and debug APK assembly passed. An isolated Android emulator verified call
presentation over the launcher and lock screen, Answer/Decline controls, camera
capture and transport, and no further frames after Video off. The emulator used
a local fixture server, not the owner's real provider session. Physical ringtone,
OEM permission behavior and provider vision responses still require a phone test.
