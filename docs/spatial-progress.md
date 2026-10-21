# Spatial subsystem checkpoint

Owner: Sajan Rai. Visible identity: Zaya. All new capture/control tools are
owner-gated and opt-in. Missing optional dependencies never gate normal startup.

## Implemented and exercised

- Local adaptive mss frame differences, foreground window class/title, dialog
  class detection and cursor/changed ROI metadata. No image saving or uploads.
- ScreenPeeler region sources reuse existing OCR/clipboard behavior.
- Optional OpenCV + MediaPipe Hand Landmarker worker, normalized hand data,
  time-based EMA, pose stability, explicit navigation/keyboard contexts.
- Palm-relative keyboard press/release hysteresis, global finger lock, focus-safe
  queued passive overlay, shared existing SendInput helpers, lifecycle stop hooks.
- Strict bounded semantic scenes, hierarchy/relationship validation, atomic
  revision-checked patches, undo/redo, selected-part context, private bounded cache.
- Nine parameterized schematic generators, basic component primitives.
- Loopback-only token-authenticated browser renderer with bounded WebSocket
  queues, reconnect replay and isolated Python state. WebGPU initialization with
  WebGL fallback, progressive component queue, vertex-targeted sand/fade effects,
  semantic picking, camera orbit/zoom, reversible exploded view, X-ray and clipping.
- Owner action discovery and selected-object instructions in the existing prompt.
- Stable-pose local hand frames now drive renderer orbit, two-open-hand zoom,
  point/poke selection, pinch translation and wrist rotation. Two pinched hands
  pulling apart request explosion. Fist/loss cancels a grab. A released grab is
  one revision-checked, selected-part-only undo transaction, gated by owner-enabled
  ACTIVE spatial tracking. Selection-only mode never manipulates.
- Optional OCR now uses Windows in-memory streams with a bounded single worker,
  at most one ROI submission every two seconds; foreground executable identity
  is resolved locally. Real synthetic-text OCR succeeded without screenshot files.
- MediaPipe and the official model are installed locally in `.venv-hands`,
  isolated from the app's OpenCV. The fixed hidden child entry point uses bounded
  JSON hand data, releases the camera on parent EOF/stop and cannot run commands.
  Actual model inference on a blank synthetic image succeeded; no camera was opened.

Build renderer: `cd spatial_renderer; npm ci; npm run build`.
Use `spatial_workspace action=open`, then `action=build generator=inline_engine
parameters_json={"cylinders":4}`. `context` returns exact selected parts.
Existing objects use `modify` or `patch` with the current `revision`.

Hand tracking requires optional `requirements-hands.txt` and an official local
MediaPipe Hand Landmarker `.task` model. Neither is installed/downloaded by normal
startup. Model instructions: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python
Use `hand_controls start` with a model path and mode; `stop` revokes typing before
releasing the camera. No physical hand/camera verification has occurred yet.

Focused tests: perception noise, keyboard no-accidental/no-duplicate presses,
tracking loss/missing dependency, GUI focus/coalescing, external trust rejection,
generator/schema limits, atomic patches/history, protocol replay/auth and renderer
reconnect. Browser preview visibly exercised an engine, X-ray and exploded view.

## Still required by the full specification

Deep code/semantic desktop context, ROI tracking across movement, complete named
gesture vocabulary/two-hand temporal gesture events,
calibration/settings persistence, shared camera arbitration with existing vision,
physical hand-driven spatial validation, annotations, selection/group/layer explosion,
custom clipping-plane rotation, proper gear/spring/fan geometry, GLB/glTF semantic
import, durable spatial session recovery across a full Zaya process restart,
measured latency/FPS and all requested physical demonstrations. Current cache
persists generated scenes, but the active session/history are in memory.

The latest owner request explicitly asks for focused deterministic test files,
superseding the earlier removal of unrelated legacy tests. No Android source was
changed in this subsystem; no APK release is needed.
