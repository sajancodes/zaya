# October 19 bug review

Reviewed the 22 supplied findings against the current checkout. Local settings,
history, linked credentials and the live running instance are preserved.

| # | Outcome |
|---|---|
| 1 | Legacy dev-agent key lookup now delegates to `gemini.api_key()`. Its generation wrapper already used pooled calls. Plural-only configuration also works in startup configuration checks. |
| 2 | Task completion locks the full update; unsupported mutated results fail safely. `ToolResult` already rejects invalid statuses on construction. Late results preserve terminal state and evidence without repeating completion alerts. |
| 3 | Task loading ignores unknown fields, supplies current defaults and recovers missing identifiers/goals or damaged JSON. Interrupted work remains paused, never replayed. |
| 4 | Tree-kill errors and timeout during the final wait are bounded and reported without crashing the worker. Cancellation is reported as requested, never falsely verified as exited. |
| 5 | Added defensive cooldown dictionary access. Normal all-cooling selection was already safe under the pool lock. |
| 6 | Retained the cap on all automatic ring attempts, including misses/declines. Those attempts still ring; counting only answered calls permits repeated interruptions. Offline requests are suppressed before creating a call. Explicit owner/test calls already bypass automatic cooldowns. Regression test covers the hourly cap. |
| 7 | Empty WhatsApp chat watermarks are now numeric zero via SQL COALESCE. The existing new-message recheck stays intact. |
| 8 | Quoted command arguments are preserved. Windows uses its native argv parser so backslashes in paths are also preserved; other platforms use shlex. |
| 9 | All config-manager setters share a locked read/update/write and synced temporary-file replacement. Failed replacement preserves the original. Unreadable configuration is never overwritten with an empty object. Temporary credential files are ignored by Git. |
| 10 | Oversized audio frames are dropped and counted; a single frame cannot exceed the queue's byte budget. |
| 11 | Not confirmed. Google's Live capability guide supports prebuilt voices generally and explicitly demonstrates Kore. No evidence justifies removing the working 3.8 rung for other voices. Existing Nika compatibility restriction remains. |
| 12 | Expiry identifies the pending instance inside resolve's lock. An old timer cannot clear or hide a newer confirmation; failed display cleanup also checks identity. |
| 13 | No change: deletion/enqueue share the same condition lock, and slot cleanup is already in finally. |
| 14 | No change: Popen and process registration are already inside the same lock acquired by cancel. There is no exposed registration gap. |
| 15 | Documented deque eviction accounting before append; tested simultaneous byte/count bounds. |
| 16 | Deadline signals cancellation onto the helper's own event loop, suppresses late results and retains its session slot until the worker exits. Thread-creation failure returns the reserved slot. Cooperative cancellation cannot forcibly kill an arbitrary blocked Python thread; retaining the slot bounds that case. |
| 17 | Discovery, host-API selection, transport results and cache publication are serialized. Rate changes invalidate cached probes and selection together. Tests open no physical audio devices. |
| 18 | Browser logs print ToolResult.summary instead of serializing data. Kept the supported legacy result adapter rather than changing every public return type. |
| 19 | Suppression intentionally emits a notification without inventing a call/session. Regression test verifies no ghost call is created. |
| 20 | Brief-enabled persistence now coerces to bool. |
| 21 | Added acoustic behavior tests across gain/reverb fixtures: pure echo is rejected and distinct speech survives. Thresholds are unchanged. Synthetic fixtures do not claim to cover every measured physical room. |
| 22 | No defect reproduced: frames already consumes generators correctly once and returns its output list. Added list/generator equivalence coverage. |

Voice compatibility reference: [Google Live API voice configuration](https://ai.google.dev/gemini-api/docs/live-api/capabilities#change-voice-and-language).

Automatic-call policy: the hourly budget counts ringing attempts. Suppressed
requests are written notifications with no answer/missed-call lifecycle. A direct
owner request uses `requested=true`; it still cannot interrupt an existing call
or pretend an offline phone is connected.

Validation: 365 desktop tests completed successfully (six skipped), including the new regression fixtures. CI-scoped Ruff checks passed. Provider calls, real room acoustics and physical phone behavior were not exercised by this offline suite.
