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
