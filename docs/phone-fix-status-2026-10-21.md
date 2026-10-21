# Phone repair status — 21 October 2026

This implements E09–E18 in the supplied extended audit, preserving the existing owner edit adding `Any` to core/mobile_bridge.py. Private state, credentials and linked devices were not changed.

| ID | Repair |
| --- | --- |
| E09 | One typed contract: action.invoke with request_id/action_id/arguments/target device/expiry, action.result with matching request ID; normalized lowercase results and flattened data for Python callers. |
| E10 | Screen requests use the same correlated capture_screen action. Real MediaProjection JPEG data returns to the requesting laptop caller; JPEG transfer is bounded. Screen descriptions route through the existing laptop multimodal tool rather than claiming local placeholder analysis. |
| E11 | notification.event and capabilities.report now have matching receivers. Notification app/sender fields are normalized; event-bus keyword arguments are used correctly. |
| E12 | Added typed volume action, corrected notification_key/package_filter arguments, normalized result data/status. SMS composer/dialer results retain the actual Android spoken outcome and do not claim message delivery or a connected call. |
| E13 | Communications always start unconfirmed regardless of model arguments. A visible phone consent activity obtains the actual owner decision; permission grants use Android's own prompt. Multiple approval stages remain separate. Requests expire and cancel on disconnect; late callbacks cannot approve another request. Duplicate request IDs do not repeat completed actions. |
| E14 | Connectivity uses live paired sessions, never generic bridge sink count. Offline tools fail promptly without simulated success. |
| E15 | An explicit notification key miss returns no match. It never falls back to a different conversation. |
| E16 | Requests select exactly one live paired device and one session; ambiguous devices fail closed, optional device_id is exposed on all mobile tools. Pending replies bind to that device and only the first final result is accepted. |
| E17 | Routine foreground startup excludes microphone and MediaProjection types. Projection promotion occurs only after system screen-capture consent; microphone promotion occurs for an answered call. Projection capture is serialized and uses fresh consent after stopping. Startup promotion failure is logged and stops the service rather than pretending it is foreground. |
| E18 | Retained cellular listener can register after permission grants, refreshes on UI resume/connection/queries and unregisters on shutdown. The deprecated callback supplies caller numbers only when Android allows them (including call-log permission); unknown/private numbers remain explicitly unknown. No caller identity is invented. |

## Old phone command replay and completion reporting

- Every desktop process has a new server_instance announced in authenticated HELLO. Android sends it with fresh commands; commands bearing an old or absent instance are rejected.
- Reconnect never resubmits previous text, including offline commands. It queries prior request status only. Unknown previous requests become failed and require a new explicit user submission.
- Tracker entries expire on in-flight queries, not only after another user message.
- Gate lifecycle transitions publish command.status, terminal states cannot be resurrected, and acknowledging cannot downgrade executing.
- complete_scope(scope, ok, error) supports explicit whole-goal completion. It must not be called merely because one tool finished or an unrelated provider turn completed. Main runtime integration is handled in the parent change.

## Verification and limits

Targeted offline Python contract tests exercise real bridge routing, wrong-device rejection, ambiguous-device failure, Android-result normalization, stale desktop-instance rejection and scope-specific terminal publication. Existing phone video regression tests are retained for the verification run; the owner requested test-file removal after checks.

Android JVM tests and debug build run locally. Physical device calls, SMS, notification replies, permission prompts, screen capture and microphone service transitions were not exercised. Android may restrict a consent activity opened from the background; the owner can open Zaya to see the pending approval, and the request expires without executing if no decision arrives. Platform validation on the owner's phone is still required. No app restart, phone action, provider request or UI approval bypass was used.

## Release compatibility repairs

Release lint identified ten error sites, repaired at their runtime boundary without a lint baseline, permission suppression, minimum-SDK increase or feature removal:

- Microphone creation handles a real SecurityException explicitly, preserving a useful permission-denied outcome.
- Ordinary notification posting checks POST_NOTIFICATIONS on Android 13+; service status updates use this same checked path.
- Incoming call screens use supported window flags on API26 and the newer activity APIs on API27+.
- Typed startForeground calls use an explicit API29 guard; older phones retain the supported two-argument call.
- Navigation-bar appearance lives in values-v27; the API26 base theme keeps its dark appearance.
- Camera and telephony hardware are explicitly optional, matching the existing capability checks and tablet/no-camera behavior.

The minimum SDK remains 26. Verification results are appended after the sequential low-worker lint, release build and JVM test runs.

Release lint rerun: **passed, zero errors** (67 non-blocking warnings). No lint issue was disabled.

Final sequential Android validation with `--max-workers=2`: **lintRelease passed (0 errors), assembleRelease passed including R8/signing/packaging, and all 100 JVM tests passed with zero failures or errors**. Tests ran before the owner-requested test-source removal. Physical phone behavior remains unverified as described above.
