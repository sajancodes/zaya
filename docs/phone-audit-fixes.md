# Phone/video audit dispositions (2026-10-19)

The supplied review includes duplicate and speculative findings. This slice covers core/mobile_calls.py, dashboard/mobile_api.py and the Android camera/call lifecycle.

## Fixed

- **30, video lag:** The preview was the same one-JPEG-per-second still capture sent to the model. Camera2 now renders a continuous native TextureView preview. YUV frames are drained continuously, with at most one bounded JPEG per second sent to Zaya. Encoding bitmaps are explicitly recycled and never exposed to Compose. The previous implementation created allocation pressure, but an indefinite bitmap leak was not proved: unreferenced objects were eligible for garbage collection.
- **33:** Call payloads now include muted/video_enabled. Android restores mute from snapshots and live mute events. Video stays explicitly opt-in and is never enabled from a snapshot. Ended calls clear both flags.
- **36, 37:** Runtime video operations are synchronized and callbacks carry a generation plus current call identity. An old camera cannot publish frames or disable a newer camera. Preview removal, backgrounding and hang-up stop capture. Camera resource cleanup runs on the camera worker and keeps pending open callbacks alive until their device can be closed.
- **77:** Video changes emit system.call.video. Android honors an explicit server-side off event without auto-starting the camera. Mute event payloads are captured under the manager lock.
- Additional defensive checks reject unknown video events, revalidate ownership/opt-in after image validation, and tolerate a full best-effort frame queue.
- Duplicate Ring events for the same currently ringing call no longer restart notification/activity delivery; the service also deduplicates repeat HELLO presentation.

## Findings that are not defects as described

- **34:** _handle_control already routes only call.video.toggle and call.video.frame into the camera handler. The handler now also checks directly for defense in depth.
- **35:** Video drain/replacement executes without await on one asyncio event loop; the alleged mid-drain race is not reproduced. Consumers can empty the queue safely. A defensive queue.Full catch was added for future producer changes.
- **78:** The throttle is already keyed by call_id and reset on video toggles. It cannot throttle a different call. A regression test now proves this.
- **79:** IncomingCallActivity already uses singleTask in the manifest. Full-screen and overlay launch paths reuse the same activity rather than creating duplicates. Repeated ringing effects were separately deduplicated.
- **80:** Audio eviction is the documented bounded low-latency policy, with existing accounting tests; it should not become an unbounded queue.
- **6, 11, 19:** Missed attempts count toward the automatic spam cap; no unsupported voice restriction is introduced; suppressed rings intentionally become notifications. Existing requested-call priority and mic suppression behavior is preserved.
- **29, 81:** Duplicate main.py relay concern is handled by the root audit slice, not this change.

## Validation

- 18 Python phone/video/call tests passed (including three new cases for payload flags, decode/hang-up interleaving, and a new call bypassing old throttling).
- 59 Android JVM tests passed (including independent YUV row/pixel stride and buffer-position cases, duplicate-ring and muted-snapshot cases).
- Android debug APK assembled and upgraded the isolated emulator from 0.3.0 to versionCode 4 without clearing its fixture pairing.
- New camera UI could not be exercised: automatic approval review rejected the emulator activity launch with the reason "blocked by policy". No alternate bypass was attempted. The emulator and fixture server were stopped. Physical camera smoothness and long-call memory behavior remain device checks; no physical owner phone or running desktop assistant was touched.
