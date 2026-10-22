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
- Local GLB/glTF 2.0 import preserves hierarchy, names, TRS/matrix transforms and
  quaternion orientation. Renderer loads actual mesh data via private opaque asset
  URLs. Imports are ASSET_BASED, not automatically engineering-authoritative.
  Remote dependencies and directory traversal are rejected. Asset bytes, semantic
  nodes, vertices/accessors and resource counts are bounded. Current import does
  not support data-URI buffers. Browser preview verified a real imported triangle
  and picked its original semantic name. Cache holds up to four imported bundles.
- Active scene, view, camera, selection and bounded undo/redo now recover from a
  private atomic JSON snapshot. Imported asset bytes persist separately in a
  bounded private SQLite cache. Invalid snapshots are retained and reported
  without blocking optional startup. Clear-history and unused-cache actions are
  explicit; source model files are never removed or rewritten.
- Existing desktop camera requests reuse the active hand worker's camera through
  explicit bounded one-shot JPEG requests. No frame is transferred by default;
  stopping tracking clears its single raw-frame reference and releases the sensor.
- Gesture engine includes stable grab/fist, poke, wrist-rotation and two-hand
  spread/close/pull events; local rendering remains independent of the LLM.
- Desktop Controls now opens a hand/spatial settings panel. Camera/FPS/mirror,
  tracking confidence and typing sensitivity persist without auto-enabling the
  camera. Pause/resume is explicit; malformed settings cannot prevent Stop.
  Hand typing refuses Zaya's own foreground process.
- Semantic labels, part/group/layer explosion and independently reversible part
  offsets, custom normalized slicing planes, related-part context and atomic
  annotation patches are implemented. Streamed NDJSON AI planning displays each
  validated part before generation finishes; errors restore the previous scene
  and partial drafts never overwrite the saved workspace. Camera orbit/zoom
  remains available during construction. Pinch edits wait until commit.
- Renderer asset requests are restricted by local-only CSP and token-protected
  WebSocket origin checks. Model extension URIs cannot request unvalidated files.
- Latest focused Python validation: 61 passed; fatal-error Ruff checks passed.
  Main and isolated hand environment dependency checks passed. TypeScript/Vite
  builds passed throughout, including the final TypeScript/Vite production build.
  Browser reload verified X-ray opacity survives materialization and labels remain
  anchored. Temporary preview servers and the testing tab were cleaned up.
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
- Integrated Vision Control Center (`Zaya · Vision & Hand Control`) with bounded
  8–12 FPS webcam preview, 21-landmark skeleton overlay with toggle, full virtual
  keyboard in KEYBOARD mode, and non-restarting mode switching across NAVIGATION,
  KEYBOARD, SPATIAL, and SELECTION. Startup state propagation resolves indefinite
  STARTING with startup timeout and immediate ACTIVE signaling. Natural language
  commands route virtual keyboard and webcam actions.

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

Physical gesture calibration/validation and latency/FPS measurements; deeper
desktop/code understanding beyond local OCR heuristics; robust ROI association
across moving/resized windows; rich gear/spring/fan geometry instead of schematic
primitive approximations; animated mechanical relationships; progressive reveal
polish for imported mesh materials; advanced glTF/data-URI/compressed texture
compatibility and embedded-texture pixel-budget hardening; all real-owner demos.

Known verification limits: no live webcam was opened and no real OS keystrokes
were injected during development. Live configured-provider NDJSON streaming was
tested with deterministic fake chunks, not a billed provider request. Clipping
planes slice geometry but do not generate filled cut caps. Browser bundle is
currently roughly 6.3 MB before gzip and needs profiling/code splitting.

The latest owner request explicitly asks for focused deterministic test files,
superseding the earlier removal of unrelated legacy tests. No Android source was
changed in this subsystem; no APK release is needed.
