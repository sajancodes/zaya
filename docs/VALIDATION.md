# Zaya validation and rollback

**Created and developed by Sajan Rai.** See [creator credits](../CREDITS.md).

Current behavior after the October 15 owner updates: conversation storage remains
continuous, but startup is fresh and history recall is on demand (five messages).
This supersedes earlier automatic provider-checkpoint/text-restoration behavior
described in the historical validation entries below.
Reply timeouts now keep the same live session and never replay actions. Explicit
local speech boundaries replace server end-of-speech detection when WebRTC VAD
is available. This also supersedes the historical stall-reconnect policy below.

Baseline: `a7daf25` on `zaya-updates`; inherited application baseline: `54733d5`.
The baseline had no automated tests. Core PyQt6, Google GenAI and sounddevice
imports passed on Windows. Live audio and external messaging require separate
canaries; imports and syntax checks do not prove those services work.

Run the regression suite with `python -m unittest discover -s tests -v`.
Tests use temporary files, processes and repositories; they do not send messages
or change personal memory. Each implementation phase is a separate commit.
Rollback with `git revert <phase-commit>` after inspecting dependent commits.
Do not reset the working tree or delete local config, memory or Hermes pairing.

## Verified on Windows, October 14, 2026

- 68 automated regression/integration tests passed. They cover real temporary
  Git commit/push SHA verification, terminal output and cancellation, Chromium
  navigation/redirect verification, UI identity and task state, WhatsApp
  identity merging, unread counts, notification deduplication, explicit reply
  modes, duplicate-send prevention, manual takeover and trust boundaries.
- Static syntax/undefined-name checks passed. Windows cp1252 memory/profile
  tests passed after removing an unsupported emoji from save logging.
- Real Gemini 3.8 Live/Nika audio worked with the application tool schema.
  A non-destructive provider-directed terminal canary returned real output and
  post-tool audio. The isolated notification voice returned 263,522 PCM bytes
  and a transcript in a separate session with no tools.
- A user-approved self-chat message was accepted by the real WhatsApp
  transport. Actual incoming contact events were persisted. After repairing
  the phone/linked-ID split, the previously missed reply was visible in the
  corrected contact conversation. No additional live contact messages were
  sent while implementing these fixes.
- The updated application started, connected to Gemini and opened its mic/
  speaker streams. The saved Hermes linked-device session reported connected.
  Existing chats were left in observation mode, with zero auto-enabled chats.
  All eight previously pending incoming messages were queued to the real Nika
  announcer and recorded as notified, without sending contact replies.

The live auto-reply path is tested with controlled transport fixtures; no new
real-contact auto-reply canary was sent during this repair. Historical inbox
coverage and recipient read receipts are not guaranteed. Voice announcements
depend on provider availability and wait for a quiet interval.

One existing plugin is intentionally rejected because `game_updater.py`
duplicates the core `game_updater` tool; diagnostics expose that exact reason.
This is separate from WhatsApp readiness.

Before repairing the private inbox, a SQLite backup was saved under the ignored
`memory/backups/` directory. To restore it, close Zaya and its owned bridge,
preserve the current database, and restore the chosen backup together with a
compatible source version. Never remove or replace Hermes pairing credentials.

## Browser closed-context recovery

The attached audit excerpt recorded browser errors as `partial`, without error
evidence. Closing an isolated persistent Chromium context and calling
`_get_page()` reproduced `BrowserContext.new_page: Target page, context or
browser has been closed`: `_launch()` reused the non-null but dead context.

Context-close and browser-disconnect events now invalidate that context. Page
acquisition and explicit navigation have bounded recovery; surviving tabs are
reused and concurrent acquisitions share one launch. Delayed close events cannot
clear a replacement context. Explicit close also clears the stopped Playwright
driver so reopening can initialize it again. Clicks, typing and form submissions
are never replayed by this recovery. Closed-target failures return `failed` with
redacted exception evidence in the runtime log, instead of legacy `partial` text.

`tests/test_browser_recovery.py` exercises real isolated persistent Chromium
sessions, local HTTP navigation after closure, tab reuse and concurrent launch,
plus bounded failure recovery, non-replayed clicks and error-result evidence.
No personal browser profile or signed-in account is used by these tests.

## Listening during media requests

Created and developed by Sajan Rai. The playback tool returned in 14–17 ms in
the local audit, but microphone audio was explicitly discarded while the voice
speaking flag was true. Playback cleared that flag only after a server turn
marker, so a tool pause could leave the microphone gated after sound ended.
An output-device RuntimeError also silently stopped only the playback worker.
Both regression tests fail against the previous committed playback code.

Playback now releases the speaking gate after 350 ms without queued audio,
retaining the device echo tail. Sustained owner speech can interrupt a reply;
its initial blocks are retained and queue mutations run on the session loop.
Server interruption events discard old queued sound and accept the next answer.
The live input queue retains at most sixteen blocks (about one second) instead of twelve seconds of
stale speech. Output failures propagate to the existing session recovery path.
This follows [Google's interruption protocol](https://ai.google.dev/gemini-api/docs/live-api/best-practices).

PortAudio input has shape `(frames, 1)`, while speaker PCM is flat. The echo
fingerprint now flattens both, avoiding a broadcast matrix and failed spectral
comparison. Tests cover real synthetic echo versus a distinct voice, retained
speech, privacy gates, congestion, session replacement, missing turn markers,
output failure, and server interruption. Room acoustics still affect separation.

The Windows microphone transport probe now allows one extra second for device
startup, rather than rejecting a working input after 350 ms. A live local probe
received 18 callbacks / 18,432 frames in 1.5 seconds; no audio was saved. A
delayed-stream fixture verifies the picker accepts this startup behavior.

Validation: all 133 local tests passed, including the existing media, audio
ducking, desktop, browser and WhatsApp tests. Ruff's error checks and
`git diff --check` passed. No live message was sent. Speaker-to-microphone
interruption in the owner's room still requires a live listening check.

## Direct replies after the first response

Live counters showed active microphone callbacks, an open input gate, successful
network sends and subsequent server transcriptions. This rules out a stopped
microphone or sender for the observed session. The saved/default configuration
enabled provider-side proactive audio, which allows speech to be ignored as
irrelevant. It is now opt-in; this owner's local setting was also set to false.
This is separate from the app's proactive notifications and WhatsApp monitoring.

A live Nika API check streamed two locally synthesized, non-personal spoken
requests in the same connection with selective audio disabled. Both received
transcriptions and audio answers (34,560 and 59,042 bytes). This verifies the
provider's consecutive-turn path; it does not replace a room-acoustics test.

`system_diagnostics` audio checks now include the locally saved voice health:
callback, queued, sent, received and transcription counts, numeric levels, input
gate and current playback state. No PCM, text, credentials or transcripts are
saved. Diagnostic file errors do not stop the microphone. Regression checks
cover the opt-in default, live config, and microphone-to-network counters.

Validation: 135 local tests and Ruff error checks passed. The restarted desktop
session reports `selective_audio: false`, active microphone callbacks, successful
network sends and an open gate after replies. The two-request live provider
check above used synthesized fixtures rather than recorded owner speech.

## Persistent conversation and startup recovery

Created and developed by Sajan Rai. Zaya now keeps a continuous chat ID, the full
local text archive, current owner request identity and provider checkpoints in
ignored `memory/conversation.db`. Commits never include this database or its
journals. Incoming transcript fragments update one durable user turn, and
closing during a response retains partial assistant text. Typed/phone text is
saved before delivery. Recent turns are shown again in the desktop chat; the
`conversation_history` tool retrieves older details with owner-only access.

Provider checkpoints are scoped to model, voice and a credential hash. Unsafe
in-flight checkpoints are cleared. Expired/rejected checkpoints and changed
credentials restore bounded recent text as explicitly historical context, with
`turn_complete=False`. Old requests and tool calls are not replayed. The full
archive and chat ID remain unchanged. An existing chat skips the fresh morning
briefing. Google documents a [two-hour resume-token window](https://ai.google.dev/gemini-api/docs/live-api/session-management).

A live Nika check remembered a synthetic marker across a closed/reopened
provider connection using a saved token. After that token was removed, another
new connection remembered it using restored local text, with the same chat ID.
These tests used a temporary database, not the owner's chat history.

Startup connection entry is bounded at 20 seconds. Constructor/worker failures
leave a visible error and redacted local diagnostic log instead of silently
leaving the character in Thinking. The updated desktop reached Connected with
an active microphone and an open sending gate.

## Comma-separated Gemini credentials

The masked editor accepts and deduplicates comma-separated keys, preserving
other saved preferences. The legacy primary-key setting still contains one
valid key for older integrations. Live sessions and central helper generations
switch configured keys on quota errors, including errors nested in background
TaskGroups. Cooldowns honor provider retry hints; exhausting the pool waits
instead of issuing a rapid retry loop. Helper HTTP requests use one SDK attempt
so credential failover owns retry behavior. Quota is project-scoped; adding
keys from the same project does not create additional quota.

Tests inject quota errors rather than deliberately exhausting real accounts.
They cover key order, deduplication, cooldown expiry, headers, nested failures,
helper failover, exhausted-pool waiting, saved settings and the actual Qt editor.
The isolated notification voice also uses the key pool and does not issue new
provider requests while all notification credentials are cooling down.

## Owner speech versus WhatsApp announcements

The announcer previously considered the owner idle three seconds after speech,
even if the main session still owed a reply. Local notification audio shared the
speaker queue, and interrupting it set the main model's interruption flag even
though the main server had no matching spoken turn to cancel.

Local speech detection now reserves the owner's turn before provider
transcription, independently of whether ducking is enabled. Announcements are
deferred until the owner's turn finishes and the speaker is idle. Speech during
synthesis invalidates the pending announcement. Interrupting notification audio
does not suppress the main model's next reply, and arriving owner response audio
takes the speaker queue back. General proactive announcements also defer to an
unanswered owner request. Inbox observation continues throughout.

A live comparison reproduced another voice-path failure: pausing PCM and sending
only a stream-end marker produced no transcription/reply. Supplying trailing
quiet made the same sample work. The sender now paces one second of generated
quiet before the stream-end marker whenever microphone delivery pauses. The
audio format explicitly declares 16 kHz. This is generated silence, never audio
captured while mute/sleep/privacy gates are closed.

The updated real main microphone-queue/send/receive methods were exercised with
two synthetic spoken requests against Nika. Both produced owner/assistant turns;
the second interrupted a local notification fixture and received an answer.
No contact message was sent and no owner's speech was saved by these checks.
This proves the streaming path; actual speaker/microphone room separation still
depends on acoustics. The watchdog behavior was corrected below after the owner
reported that the earlier reconnects still did not restore replies.

Final validation: all 162 local tests passed, plus the live spoken-input,
notification-interruption, provider-resume and text-fallback checks described
above. Ruff error checks and whitespace checks passed. Real rate-limit failover
was simulated with injected provider errors; no account quota was deliberately
exhausted. The owner's configuration currently contains one key, so additional
credentials must be entered in the masked editor to use cross-key failover.

## Stalled provider checkpoint: October 15 follow-up

The real saved checkpoint reproduced the owner's failure: with the full
production prompt and 41 tools, the provider accepted and transcribed a spoken
fixture but produced no reply within 25 seconds, even after trailing quiet and
an audio-stream-end marker. A fresh connection with the same production config
and the same restored local history answered both spoken fixtures. Diagnostic
tool responses were stubbed; no contact messages or computer actions ran.

Provider checkpoint scope is now versioned so pre-fix handles cannot reopen the
stuck provider state. Local chat history and its ID remain intact. If another
reply stalls, the watchdog discards the native handle and restores saved text
once, asking for a fresh request rather than replaying an action. If the fresh
connection also stalls, automatic recovery stops with a visible error instead
of reconnecting forever. Successful model output or an explicit settings
reconnect resets this recovery allowance. The owner then confirmed voice replies
were working. Owner-only command enforcement and confirmation remain unchanged.

## Quiet WhatsApp auto mode

The owner may enable `start_auto` without a chat via “WhatsApp auto” and related
requests. Current non-paused direct chats and future direct chats inherit auto;
groups keep their own mode. The setting persists locally. Switching modes never
enqueues old messages. Auto previews are consumed locally without spoken text,
including messages arriving while announcements are busy, so turning auto off
cannot read an old backlog. `stop_auto` returns direct auto chats to observation.
The existing complete-feed, deduplication, sensitive-reply and manual-takeover
checks remain. In-flight generations recheck mode before sending. Every reply
has an explicit Zaya/Sajan Rai assistant label; external text receives no tools.

Eight added integration tests cover the real action/store/worker/announcer path,
new contacts, restart persistence, quiet previews, global stop, group/paused
exclusion, manual takeover, mode changes during generation, exact-chat scope,
offline reporting and rejection of non-owner mode changes. Transport is mocked;
these tests send no actual WhatsApp messages.

A subsequent full-config live spoken-command comparison found another context
boundary problem: restoring a lone historical `user` turn with
`turn_complete=False` could transcribe "WhatsApp auto mode" without invoking
the tool or answering. Ending the restored exchange with a model acknowledgment
before accepting new audio made both spoken "WhatsApp auto mode" and "Stop
WhatsApp auto mode" invoke `start_auto` / `stop_auto` without a chat argument.
The same production prompt, 41 tools, saved history, and audio fixtures were used.
The acknowledgment is provider context only, not a saved chat reply or an action.
Checkpoint scope was advanced to avoid reopening the old unfinished history
state. The live transport was stubbed for tools; no WhatsApp messages were sent.

## Regular Brave profile for ordinary links

The owner supplied a Brave screenshot showing GitHub signed out and a 404 for
the private repository. Navigation previously switched to Playwright whenever
`verify=true` or a cached automation session existed; `git_control open_remote`
always set `verify=true`. That could silently select the separate automation
profile after a regular-profile lock failure.

Opening, searching and new tabs now default to native launch, independent of
cached sessions and `verify`. Only explicit `mode=automation` navigates a
controlled profile. A saved `preferred_browser` is honored, with explicit owner
browser choices overriding it. Repository opening passes the exact URL to the
native route. Native launches do not claim verified navigation or authentication.
No cookies are read/copied and no regular browser is closed or relaunched with
debugging flags. Seven tests cover native routing with a cached session and
verify flag, preferred/explicit browsers, the actual Brave launch argument list,
explicit automation, launch failure, Git remote routing and non-owner rejection.

The local preferred browser was set to Brave while preserving the other private
settings. A real native launch of the exact GitHub repository used the installed
Brave executable with only the URL, without automation/profile/debug flags. The
launch is verified as submitted, not as authenticated access to the private page.
All 179 local tests, Ruff error checks and Git whitespace checks passed after
these changes. Hosted GitHub checks remain blocked by the account's billing
limit recorded earlier; local results are separate from hosted checks.

## Quiet task failures and ordinary WhatsApp follow-ups

Removed the generic `task.failed` speech subscription and queue from the
notification manager. Task events, activity labels and durable runtime failures
remain available. A regression test publishes a failure event, verifies another
subscriber still receives it, verifies no spoken item is created, and verifies
normal inbox notifications continue.

The owner's unanswered “Where is he?” was present as a complete native inbound
message; its chat remained in auto mode. The classifier had marked it
`needs_owner=true` because the answer required personal knowledge, so the worker
correctly held it under the previous policy before generating any response.
Unknown harmless facts now allow a truthful uncertainty response instead of
mandatory silence. Neither classification nor generation authorizes discovering
or guessing whereabouts, availability or intentions. Consequential decisions,
commitments, sensitive disclosures and security/money actions remain held.

A real isolated model check classified the synthetic “Where is he?” fixture as
normal (score 20, `needs_owner=false`) and generated “I do not know where Sajan
is right now. You can leave a message for him here.” No transport was constructed
and no contact message was sent. Regression coverage runs three consecutive
incoming turns through the real classifier/generator wrappers, reply worker,
adapter and durable send state with model/transport fixtures. All three receive
one reply, confirmed native echoes preserve auto mode, and owner decisions or
classifier outages still produce no send.

## Current activity, selective owner relays, and on-demand History

The WhatsApp reply model now receives a small `shared_current_activity` list:
current display playback after Qt reports PlayingState, verified project work,
or an explicit owner activity set through the owner-only `session_activity` tool.
Media clears on pause/stop; other activity expires. State is in memory and never
imports old conversation turns, private profiles, files, commands or credentials.
Private path/link/credential values are rejected or reduced to generic media.
Contacts cannot alter this state or reach privileged tools.

Semantic classification adds `notify_owner` for pass-along requests and urgent
messages. A durable alert is queued before any acknowledgment. Its separate
delivery flag is independent of ordinary auto-chat preview suppression, so
quiet mode cannot consume the owner relay. The isolated tool-free voice reads
the sender/context after owner speech finishes. Delivery is marked once;
retries and restarts retain pending relays. Normal auto conversations, manual
takeover chatter under global auto, and generic operator failures remain silent.

Live isolated generation checks used synthetic activity and messages, without
a messaging transport: Sanam playback produced a listening-to-Sanam reply;
project activity produced a working-on-a-project reply; a dinner pass-along
request classified `notify_owner=true` and acknowledged only queued status.
Worker tests cover durable relay recovery, quiet ordinary chat, urgent owner
decisions without commitments, and task failures without generic speech. Qt
integration verifies media state updates and clearing.

Fresh startup now checks only whether the local archive exists; it neither
loads old message bodies nor sends history to Gemini. A saved provider handle is
not loaded into a new process, and reconnect/exit no longer uploads the whole
session for automatic summarization. In-process transient reconnects can still
resume the current provider session. Last Conversation History is a separate,
on-demand local view with batch insertion. Owner-requested recall/search returns
at most five messages and 4,000 text characters, always labeled historical data.
Regression tests verify the cap, unchanged full archive, no saved-token loading,
and history views without typing queues or live bubbles.

## Speech turns and tool continuity: October 15 follow-up

The owner's latest local history contained consecutive owner wake/greeting
messages with no following assistant response. Health still showed a live
microphone. A fresh live probe reproduced the failure with the full production
configuration (42 tools): the server reported speech start but no transcription
or response after local silence and `audio_stream_end`. Explicit local activity
start/end markers with automatic server VAD disabled produced responses.
This is a supported [Gemini Live input mode](https://ai.google.dev/gemini-api/docs/live-api/capabilities#disable-automatic-vad).

The microphone keeps capturing. Local WebRTC detection retains six blocks of
opening audio, closes each turn after 900 ms without detected speech, and sends
explicit activity boundaries. Idle silence does not occupy an input turn.
If captured packets pause, generated quiet closes the open turn. Without the
local detector dependency, the existing server VAD input path remains available.
Room acoustics and quiet speech still affect detection; synthetic audio does
not establish performance for every microphone or background song.

Tool batches run in session-owned workers while the receive loop processes new
speech, interrupts, and cancellation messages. Workers keep the initiating owner
scope/goal, skip canceled pending calls, discard canceled results, and reject
duplicate call IDs. Closing the connection cancels workers. Already executing
threaded side effects cannot be undone by cancellation; durable operation IDs
remain authoritative and actions are never automatically replayed on timeout.

The final live probe sent three synthetic spoken requests through the real
microphone callback, sender, and receiver with continuous silence callbacks
between phrases. It used the production configuration, no history upload, and
stubbed external actions. The media request selected the exact Darshan Raval
song with native Brave as destination; the next spoken answer recalled that
song; the third answered two plus two. All three completed in one connection,
with 441 microphone callbacks and four explicit input turns. No real media
launch or message send occurred in this probe.

Browser dispatch also enforces an explicit owner browser destination even when
the model omits it. Moving display media reuses the current source. Browser
lookup resolves a YouTube watch page or falls back to matching YouTube results;
native launch is still reported as unverified playback. Superseded resolutions
do not open the canceled browser request.

The owner's ignored local key file contains four effective Gemini keys. Existing
key selection reloads that file on each selection and rotates on provider quota
errors, respecting cooldowns for live, helper, and notification requests. Tests
use fake keys to verify rotation and newly edited keys without exposing secrets.
Multiple keys cannot bypass shared project quota.

Validation: 207 regression/integration tests passed in 73.881 seconds. Ruff
error checks and `git diff --check` passed. The live three-request probe passed
separately; actual speaker-room microphone behavior remains an owner check.

## Phone companion: the same runtime, one more interface

`mobile/android/` is a native Kotlin/Compose app; the laptop side lives in
`core/mobile_protocol.py`, `core/mobile_bridge.py`, `core/mobile_calls.py`,
`core/remote_commands.py`, `core/device_registry.py`, `actions/mobile_call.py`
and `dashboard/mobile_api.py` registered onto the existing dashboard app. No new
server, session, memory store, task runtime or WhatsApp worker was added.

Four earlier defects were reproduced and fixed with the runtime's own behaviour
preserved:

- A remote dashboard/phone command now begins a fresh owner goal and scope per
  command (`submitted → acknowledged → executing → completed/failed`, request-id
  dedupe, 2.5 s same-text folding) instead of reusing the desktop's last goal.
- The dashboard's transport encryption derived a different AES salt on the server
  than the browser used; `ZAYA-DASHBOARD-v1` is now the derivation on both sides,
  with the legacy salt accepted only for decrypting an existing session.
- Paired devices are stored in `memory/zaya_runtime.db` as PBKDF2-SHA256 hashes
  and survive restarts; a failed check is indistinguishable from an unknown
  device, and repeated failures lock the device out for a cooldown.
- Both audio queues are bounded by bytes, not frames, and drop the *oldest*
  audio; a dead or slow phone cannot stall the desktop's audio loop, and the
  control socket, the voice socket, event delivery and command execution each
  fail independently.

The phone never decides an emotion or a state: `zaya.state` is composed on the
laptop from `zaya.state.changed` plus `avatar.emotion` and rendered verbatim, and
contact text reaching the phone cannot enter the command queue. Voice runs as raw
PCM16 on two separate sockets (16 kHz up, 24 kHz down) with an app-level ping and
a stale-link threshold, and calls ring only for P0/P1 while a missed call leaves
one summary notification that never repeats.

Validation at the time of writing: the full offline suite passed (444 tests, 6
skipped), 34 of them driving the mobile routes, pairing, revocation and both
WebSockets through the real FastAPI app; a separate 48-test JVM suite covers the
phone-side logic (envelope parsing, request dedupe, backoff bounds, the audio byte
budget and every laptop event → screen transition) with no device or emulator;
`:app:assembleDebug` builds the APK with the committed Gradle wrapper. The
temporary phone-companion Python tests were removed after their final
verification run, per owner preference; the JVM suite stays in the app module,
where it needs no device.

The JVM suite found one real bug: `CommandTracker.prune` compared an absolute
cutoff against an entry's age, so with a real clock no entry ever expired and with
a small clock every entry was deleted — a double-tap could then run twice. It now
compares ages, and the regression is pinned by a test that advances a fake clock.

