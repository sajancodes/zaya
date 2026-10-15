# Zaya validation and rollback

**Created and developed by Sajan Rai.** See [creator credits](../CREDITS.md).

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
