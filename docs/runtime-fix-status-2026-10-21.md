# Runtime and memory repairs — 21 October 2026

| Finding | Repair and offline evidence |
| --- | --- |
| E01 | Durable SQLite request reservations precede invocation. Concurrent duplicates return an in-progress/uncertain result; successful effects retain cached evidence. Cancellation and exceptions do not release an uncertain invocation for automatic repetition. Concurrent and cancelled fixtures passed. |
| E02 | Mission scope checks classify the selected action. File deletion, file execution, Git push, profile mutation and browser interaction cannot inherit a tool's read permission. Read-only/list fixtures passed alongside rejected mutation cases. |
| E03 | Retry updates target the actual failed step and persist a three-attempt budget. A failed first step retried three times; an already completed second step remained completed. |
| E04 | Terminal steps reach their existing confirmation gate. Termination steps use the canonical interface gate with an originating task ID. A model's `approved` flag cannot grant permission. Mission continuation requires the real task's completed record, so the confirmed operation is skipped instead of run again. Real-interface-callback fixture executed one fake effect exactly once; external trust was rejected. Gate cancellation binds to the originating task identity. |
| E05 | Unknown or absent checks remain unverified. Explicit file checks verify a real file; process checks match exact names. Unrelated step output cannot prove a check. |
| E06 | Restart recovery scans all persisted tasks separately from bounded UI listings. A store with over 200 unfinished tasks paused its oldest task. |
| E07 | Scheduler reloads cancellation/delivery state after waiting and before notifying. Cancellation during a fake wait submitted no notification. |
| E08 | WhatsApp shutdown sets the stop signal before coordinating the lifecycle lock. Startup checks that signal before publishing a new bridge; a late bridge is closed. A blocked-start/close fixture left no published bridge. Transport and workers are cleared on shutdown. |
| E35 | JSON read-modify-write operations share a reentrant lock and atomic, flushed replacement. Session updates use the same writer. Twenty concurrent updates survived in JSON and SQLite; an injected replacement failure preserved the original JSON and did not update the index. Corrupt JSON is not overwritten by a mutation. |
| E36 | Forget removes and verifies removal from the knowledge index before removing the JSON fact, under the same memory lock used by recall. Successful forget cannot return the old indexed fact. Failure is surfaced rather than reported as successful forgetting. |
| E37 | Shared confidence/expiry policy filters JSON prompt values, UI facts and recall fallback. SQLite timestamps use time-aware expiry comparison. An expired fact remained absent with the SQLite search deliberately unavailable. |
| E38 | Only accepted, normalized changed entries are indexed; low-confidence inputs are rejected by both stores and legacy low-confidence SQL facts are excluded from search. Metadata-only source/expiry/confidence changes persist. |

Verification before the owner-requested test removal: 48 acceptance and existing
runtime/confirmation/reminder/knowledge/WhatsApp-recovery tests completed:
47 passed and one skipped. This includes 14 new focused acceptance fixtures.
Scoped syntax/undefined-name checks passed.
Fixtures used temporary files and databases, fake tools and notifications, and
an in-memory task store. No live provider, contact, microphone or owner database
was used by these checks. Physical confirmation UI, scheduler delivery and
WhatsApp reconnection still require an application/device check after restart.
