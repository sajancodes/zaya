# Continue Zaya spatial intelligence work

Work in `C:\Users\ab429\Desktop\Zaya` on `main`. Read AGENTS.md, then only
`docs/spatial-progress.md` and `docs/spatial-intelligence-spec.md`. The latter is
the owner's full original 42-phase request. Do not re-audit the entire repository,
rewrite working subsystems or restart this implementation from scratch.

Preserve Zaya branding and Sajan Rai attribution. Git author must be
`sajancodes <ab4290025@gmail.com>`; verify `git var GIT_AUTHOR_IDENT`. Commit and
push coherent verified changes directly to main without force pushes. Do not
sync the IRIS branch. Preserve untracked `tools/calculator.py` and `zaya.cmd`.
Never stage config, memory databases, credentials, logs, generated models, cached
assets or local environments. Owner trust/confirmation and all existing voice,
phone, reminder and WhatsApp behavior must stay intact. No Android source changed;
no APK release is needed for this subsystem.

## Implemented checkpoints

- e8c400f: opt-in perception and safe virtual-keyboard foundation.
- 535ca5e: semantic scenes, strict patching, isolated browser renderer.
- bbdc783: isolated MediaPipe inference, local hand-to-spatial controls and OCR.
- 18575b3: bounded semantic GLB/glTF import and real mesh rendering.
- 96621b2: workspace/asset persistence and camera sharing.
- The latest main commit adds settings UI, streamed AI planning, annotations,
  scoped explosion/custom clipping, interaction safeguards and this handoff.

No LLM runs in the hand interaction loop. Camera stays off at startup. MediaPipe
0.10.35 and OpenCV-contrib 4.14.0.94 are installed in `.venv-hands` to avoid changing
the app's OpenCV. The official 7,819,105-byte Hand Landmarker model is at
`models/hand_landmarker.task` (ignored). Recreate with `tools/setup_hands.ps1`.
Actual MediaPipe inference on a synthetic blank frame and actual in-memory
Windows OCR on synthetic text succeeded without opening the webcam.

## Existing interfaces to extend

- `actions/hand_controls.py`: start/stop/pause/resume/configure/settings/status;
  explicit NAVIGATION, KEYBOARD, SPATIAL and SELECTION modes.
- `core/gesture/`: normalized hand models, EMA, deterministic gesture states,
  palm-relative keyboard gate/lock, isolated fixed child, one-shot camera sharing,
  saved settings and Qt controls. Existing SendInput helpers remain in
  `actions/ghost_keyboard.py`. Qt passive overlays never accept focus; hand typing
  refuses Zaya's own process. Start/stop authorization must never come from
  external messages, imported scene metadata or perceived screen text.
- `actions/display_perception.py`, `core/perception/`: adaptive local mss capture,
  frame differences, foreground app/title, persistent relevant ROI and bounded
  in-memory OCR. Text timestamps are separate from frame timestamps.
- `core/spatial/`: strict bounded scenes (250 parts/depth12/100 patch operations),
  stable IDs/relationships/labels, revision checks, undo/redo, persistent sessions,
  bounded private generated/asset caches and structured planner. Streamed NDJSON
  validates each part, shows it progressively and restores the previous scene if
  any record fails. Only a complete scene is saved. Editing uses patches.
- `services/spatial_server.py`: loopback-only token/origin/host checks; bounded
  latest-state queues; renderer telemetry, selection, view changes and owner-
  enabled spatial manipulation. No shell/system commands accepted by renderer.
- `spatial_renderer/`: Babylon.js + TypeScript/Vite, WebGPU initialization with
  WebGL fallback, semantic picking, progressive queue, vertex-targeted sand/fade,
  dissolve, hand orbit/zoom/grab/wrist rotation/poke selection, reversible view
  effects and labels. Asset import preserves real mesh data/names/hierarchy/TRS.

Start renderer: `cd spatial_renderer; npm ci; npm run build`, then owner tool
`spatial_workspace action=open`; build with generator `inline_engine` and
`parameters_json={"cylinders":4}`. General prompts use streamed AI planning.
Use desktop Controls > Hand controls & 3D workspace to explicitly enable hands.

## Verification already done

61 focused tests passed, including open-palm/hover zero keys; one poke/one key;
no lateral repeat while locked; retraction/reacquisition; own-UI focus guard;
missing optional runtime; external-trust rejection; schema limits; rollback;
undo/redo; protocol auth/replay/reconnect; actual GLB/glTF binary/hierarchy handling;
saved scene and asset recovery; camera sharing; scoped views/labels; partial
stream delivery and failed-stream restoration; inline-four to V8 patch retaining
compatible IDs and resizing the casing. Fatal-error Ruff checks and both Python
environment dependency checks passed.

Browser checks visibly rendered the engine, X-ray, exploded view, a named imported
triangle and an anchored semantic label. Proof images are local ignored artifacts:
`dist/spatial-preview.png`, `dist/spatial-import.png`. Do not claim these prove
physical hands, typing into real applications or 60 FPS/80 ms end-to-end latency.
The renderer's last fade fix uses mesh visibility, keeping X-ray material opacity
independent of construction animation. Final browser reload confirmed that fix:
the casing stayed transparent after construction and its semantic label remained
anchored. Final TypeScript/Vite build succeeded. Temporary preview servers/tabs
were cleaned up; open the real workspace through Zaya after restarting her.

## Remaining work, in priority order

1. With the owner present, exercise webcam modes and all ten original demos.
   Tune palm-relative depth, thumb/finger classification, confidence/EMA and
   handedness identity on real hands. Verify real SendInput in a disposable text
   editor: open palm and hover must produce zero keys; poke once, hold, slide to
   another key, retract, repeat, lose/reacquire tracking. Never test in a shell,
   production editor buffer or messaging app. Verify modifier latching/feedback.
2. Profile actual capture/inference/IPC/WebSocket/render latency and FPS. Current
   telemetry reports renderer FPS and camera state, not full physical latency.
   Exercise simultaneous voice, phone video and explicit desktop-camera capture;
   confirm camera worker shutdown, parent EOF and bounded-frame behavior.
3. Run one configured-provider streamed planning request and a natural-language
   modification. Verify model NDJSON compliance, streaming interruption rollback,
   exact selected-object context and an evolving four-cylinder-to-V8 scene without
   clearing compatible components. Deterministic fixtures cover these paths;
   live provider output has not been tested.
4. Add richer reusable geometry for gears/screws/springs/fans and optional local
   motion relationships. Existing parts are honestly labeled SCHEMATIC; do not
   relabel them engineering-accurate. Add filled cut caps if a solid section is
   needed; current custom planes clip but do not cap.
5. Harden/import-test nested transformed/skinned/animated glTF assets, multiple
   scenes, data-URI buffers and compressed textures. Current parser rejects remote
   URIs/traversal, bounds bytes/nodes/accessors and external image pixels, but
   embedded GLB image pixel budgets still need explicit validation. CSP blocks
   remote decoder downloads; bundle approved decoders locally if needed.
6. Improve ROI association across moving windows and deeper code/error semantics
   beyond heuristic OCR. Keep capture local; no continuous image saving/uploads.
   Add optional debug-landmark visualization and physical calibration guidance.
7. Renderer profiling/code splitting (bundle about 6.3 MB raw), imported-part
   progressive materialization polish and browser context-loss stress tests.
   Stress malformed/over-budget data, simultaneous view changes, reconnect during
   construction, cancellation/shutdown and private-cache disk failures.

Run only relevant focused checks as you change these paths, not a broad unrelated
audit or full legacy suite. Current tests are the new requested deterministic
subsystem tests; do not delete them based on the earlier legacy-test cleanup.
Report material verification gaps candidly, commit/push verified changes and
keep this progress document accurate.
