You already have full context of the Zaya codebase and its current architecture.

Do NOT spend tokens re-auditing or re-inspecting the whole repository.

Do NOT begin with a repository review.

Do NOT produce another architecture analysis before coding.

Use the existing context you already have and start implementation directly.

Only read a file when you are about to modify it or need a specific interface from it.

# OBJECTIVE

Build Zaya's new Spatial Intelligence, Continuous Perception and Hand Interaction subsystem.

The finished system must provide:

1. Continuous desktop perception.
2. Webcam-based hand tracking.
3. Deterministic gesture recognition.
4. Gesture-controlled virtual keyboard.
5. Upgraded ghost overlays.
6. Real-time AI-generated 3D spatial workspace.
7. Progressive live construction of 3D objects.
8. Sand/particle materialization and dissolution.
9. Semantic 3D parts and relationships.
10. Hand-controlled rotation, zoom, selection, grabbing and manipulation.
11. Exploded views.
12. X-ray/transparency modes.
13. Cross-section/slice views.
14. Voice + hand combined interaction.
15. Natural-language modification of existing 3D structures.
16. Scene patching instead of unnecessary full regeneration.
17. GLB/glTF support.
18. Scene caching.
19. Renderer failure isolation.
20. Low-latency local interaction independent of the LLM.

# EXISTING COMPONENTS

These already exist.

Do NOT recreate them from scratch:

- `actions/screen_processor.py`
- `actions/screen_peeler.py`
- `actions/ghost_keyboard.py`
- `actions/ghost_overlay.py`
- `core/ghost_overlay.py`
- `core/display_service.py`
- Zaya's TOOL/action discovery system
- owner execution policy
- ToolResult system
- PyQt6 UI
- OpenCV
- mss screen capture
- Win32 SendInput keyboard injection
- FastAPI/Uvicorn infrastructure

Extend them where necessary.

Preserve their current public behavior.

# CORE SYSTEM ARCHITECTURE

Implement this architecture:

```text
                    ZAYA
                     │
       ┌─────────────┼─────────────┐
       │             │             │
     Voice         Screen        Camera
       │             │             │
       │        Perception       MediaPipe
       │             │             │
       └─────────────┼─────────────┘
                     │
               Context Layer
                     │
                     ▼
               Zaya Reasoning
                     │
                     ▼
           Semantic Scene Graph
                     │
                     ▼
               Scene Patches
                     │
                     ▼
             Spatial Renderer
```

Real-time hand movement must take a separate low-latency path:

```text
Camera
→ OpenCV
→ MediaPipe
→ Gesture Engine
→ Spatial Controller
→ Renderer
```

The LLM MUST NOT sit in this loop.

# REQUIRED MODULE STRUCTURE

Create approximately:

```text
core/
  perception/
    __init__.py
    screen_perception.py
    frame_diff.py
    perception_state.py
    roi_tracker.py

  gesture/
    __init__.py
    hand_tracker.py
    hand_model.py
    gesture_engine.py
    gesture_state.py
    smoothing.py
    calibration.py
    virtual_keyboard.py

  spatial/
    __init__.py
    schema.py
    scene_graph.py
    scene_planner.py
    scene_patcher.py
    component_library.py
    procedural_geometry.py
    spatial_session.py
    spatial_cache.py
    spatial_protocol.py

actions/
  spatial_workspace.py
  hand_controls.py
  display_perception.py

services/
  spatial_server.py

spatial_renderer/
  package.json
  vite.config.ts
  src/
    main.ts
    engine/
      renderer.ts
      connection.ts
      protocol.ts
      sceneManager.ts
      cameraController.ts
      selection.ts
      progressiveBuilder.ts
      particleMaterializer.ts
      explodeController.ts
      xrayController.ts
      sliceController.ts
      annotations.ts
      performanceManager.ts

tests/
  test_screen_perception.py
  test_hand_tracker.py
  test_gesture_engine.py
  test_virtual_keyboard.py
  test_spatial_schema.py
  test_scene_graph.py
  test_scene_patcher.py
  test_spatial_protocol.py
  test_spatial_session.py
```

You may adapt filenames only when integration with current Zaya clearly requires it.

Do not collapse unrelated responsibilities into giant files.

---

# PHASE 1 — CONTINUOUS SCREEN PERCEPTION

Build a local continuous screen-understanding subsystem.

Reuse Zaya's existing mss capture path.

Target lightweight capture around:

```text
10–15 FPS
```

This is NOT continuous LLM vision.

Pipeline:

```text
screen frame
↓
cheap frame comparison
↓
meaningful change detection
↓
changed-region extraction
↓
optional OCR
↓
PerceptionState update
```

Detect:

- foreground application
- foreground window title
- significant visual changes
- new dialogs
- new error regions
- important visible text
- currently relevant ROI
- cursor-area context where practical

Maintain:

```python
PerceptionState(
    foreground_app,
    foreground_title,
    activity,
    visible_text,
    errors,
    changed_regions,
    cursor_region,
    revision,
    last_updated,
)
```

Do not constantly send screenshots to an AI.

Do not continuously save screenshots.

Ignore insignificant visual noise such as:

- cursor blinking
- tiny animations
- antialiasing changes
- insignificant frame differences

Use adaptive capture:

```text
active screen → normal frequency
static screen → lower processing frequency
major change → temporary increased attention
```

---

# PHASE 2 — SCREENPEELER UPGRADE

Extend the existing ScreenPeeler.

It should support:

```text
explicit coordinates
cursor region
active window
tracked ROI
full monitor
```

ScreenPeeler should perform deeper inspection than the continuous perception loop.

Continuous perception:

```text
eyes
```

ScreenPeeler:

```text
magnifying glass
```

It may return:

- OCR text
- detected code
- region bounds
- image metadata
- semantic description when deeper vision is requested

Do not make ScreenPeeler itself the continuous frame loop.

---

# PHASE 3 — HAND TRACKING

Add MediaPipe Hand Landmarker.

OpenCV owns webcam acquisition.

Support:

```text
1–2 hands
```

Normalize MediaPipe output into Zaya-owned structures.

Example:

```python
HandState(
    hand_id,
    handedness,
    landmarks,
    world_landmarks,
    palm_center,
    palm_normal,
    finger_states,
    velocity,
    confidence,
)
```

Do not pass raw MediaPipe objects throughout the project.

Camera states:

```text
OFF
STARTING
ACTIVE
PAUSED
ERROR
```

Camera must release properly.

If MediaPipe is unavailable:

```text
normal Zaya still starts
hand controls disabled only
```

---

# PHASE 4 — LANDMARK SMOOTHING

Raw landmarks are too noisy.

Implement smoothing for:

- index fingertip
- thumb fingertip
- palm center
- palm orientation
- relative Z
- pinch distance
- hand velocity

Use:

```text
EMA
```

or preferably:

```text
One Euro filter
```

if implemented cleanly.

Do not over-smooth and introduce obvious lag.

---

# PHASE 5 — GESTURE ENGINE

Build a deterministic gesture engine.

Initial gestures:

```text
OPEN_PALM
POINT
INDEX_ONLY
PINCH
GRAB
FIST
POKE
TWO_HAND_SPREAD
TWO_HAND_CLOSE
TWO_HAND_PULL
WRIST_ROTATE
```

Each gesture requires:

```text
candidate
→ stability period
→ active
→ exit
→ cooldown
```

Never trigger important actions from one frame.

Each gesture should expose:

```python
GestureEvent(
    type,
    hand_id,
    confidence,
    timestamp,
    position,
    delta,
    metadata,
)
```

---

# PHASE 6 — INTERACTION MODES

Implement explicit interaction contexts:

```text
DISABLED
NAVIGATION
KEYBOARD
SPATIAL
SELECTION
```

A gesture's meaning depends on mode.

Example:

```text
OPEN_PALM + move

KEYBOARD mode
→ move hover cursor

SPATIAL mode
→ orbit camera
```

Do not allow simultaneous conflicting interpretations.

---

# PHASE 7 — VIRTUAL KEYBOARD

Build an on-screen virtual keyboard controlled by hand gestures.

Core behavior:

## Open palm

```text
navigation only
```

The user can freely move their entire hand across the keyboard.

NO KEY MAY FIRE.

## Index-only pose

When:

```text
index extended
middle curled
ring curled
pinky curled
```

typing mode becomes a candidate.

Require the pose to remain stable for approximately:

```text
100–150 ms
```

Then keyboard becomes:

```text
ARMED
```

## Hover

Moving the index fingertip over a key:

```text
only highlights it
```

Still no key event.

## Press

A key press requires ALL of:

```text
INDEX_ONLY active
same key targeted
target stable
forward index velocity
palm-relative depth movement
press plane crossed
finger not locked
```

Then send:

```text
exactly ONE key press
```

through existing `ghost_keyboard`/SendInput logic.

---

# PHASE 8 — PREVENT ACCIDENTAL KEY PRESSES

Do NOT use:

```python
if index_tip.z < threshold:
    press()
```

This is unacceptable.

Moving the whole hand toward the camera would trigger it.

Instead calculate index depth relative to the palm.

Build a palm reference plane using landmarks such as:

```text
wrist
index MCP
middle MCP
pinky MCP
```

Determine palm normal.

Calculate fingertip displacement relative to the palm.

A poke should mean:

```text
palm remains roughly stable
+
index fingertip moves significantly forward
```

Whole-hand movement:

```text
palm moves
+
finger moves similarly
→ NOT poke
```

---

# PHASE 9 — DUPLICATE PRESS PROTECTION

Use a state machine:

```text
READY
↓
HOVER
↓
ARMED
↓
PRESS
↓
LOCKED
↓
RETRACT
↓
READY
```

Once a press occurs:

```text
lock the entire index finger
```

While locked:

- same key cannot repeat
- another key cannot fire
- lateral movement cannot trigger anything

Require retraction past a separate release threshold.

Use hysteresis.

Example concept:

```text
press plane   = deeper threshold
release plane = shallower threshold
```

Do not use the same threshold for press/release.

Also use a small secondary debounce timeout.

---

# PHASE 10 — KEYBOARD LAYOUT

Support:

```text
A-Z
0-9
Space
Enter
Backspace
Shift
Ctrl
Alt
Tab
Esc
Arrow keys
```

Create a reusable model:

```python
VirtualKey(
    id,
    label,
    output,
    bounds,
    row,
    modifier,
)
```

Layouts should not depend on rendering code.

---

# PHASE 11 — KEYBOARD VISUAL FEEDBACK

Display states:

```text
idle
hover
armed
pressing
pressed
locked
```

Example:

```text
H
```

then hover:

```text
[ H ]
```

then press progress:

```text
[ H ↓ ]
```

then successful press:

```text
[ ✓ H ]
```

Feedback must make it obvious whether a real OS key was sent.

---

# PHASE 12 — GHOST KEYBOARD INTEGRATION

Do NOT rewrite Windows keyboard injection.

Existing `actions/ghost_keyboard.py` already uses SendInput.

Refactor reusable internal functions only if necessary.

Virtual keyboard output ultimately calls the same low-level injection path.

Preserve current action behavior.

---

# PHASE 13 — GHOST OVERLAY UPGRADE

Extend current Qt ghost overlay.

Support modes:

```text
quick_command
context_hint
virtual_keyboard
selection_label
warning
spatial_status
```

Required properties:

```text
anchor
position
content
interactive/passive
timeout
visible
```

Passive overlays:

```text
must not steal focus
```

The virtual keyboard overlay must never become the active window receiving its own generated keystrokes.

All Qt mutation stays on the GUI thread.

---

# PHASE 14 — SPATIAL SCENE GRAPH

The spatial scene graph is the source of truth.

The renderer is NOT.

Create strict schemas.

Scene:

```python
SpatialScene(
    scene_id,
    name,
    revision,
    accuracy,
    parts,
    relationships,
    metadata,
)
```

Part:

```python
SpatialPart(
    id,
    name,
    kind,
    parent_id,
    children,
    transform,
    geometry,
    material,
    layer,
    relationships,
    visible,
    metadata,
)
```

Every visible meaningful object must have a stable semantic part ID.

---

# PHASE 15 — ACCURACY CLASSIFICATION

Every generated scene gets:

```text
SCHEMATIC
REFERENCE_APPROXIMATION
ASSET_BASED
ENGINEERING_SOURCE
```

Never imply generated approximations are mechanically exact.

Example:

```text
Zaya generates a jet engine from general knowledge
→ SCHEMATIC
```

Imported authoritative CAD-like source:

```text
→ ENGINEERING_SOURCE
```

where justified.

---

# PHASE 16 — PROCEDURAL COMPONENT LIBRARY

Implement reusable primitives:

```text
box
sphere
cylinder
cone
tube
torus
plate
rod
```

Mechanical components:

```text
bolt
screw
nut
washer
shaft
bearing
gear
spring
piston
connecting_rod
valve
pipe
housing
fan
wheel
```

Electrical:

```text
wire
pcb
chip
connector
battery
coil
motor
```

These components must be parameterized.

Example:

```python
create_bolt(
    radius,
    length,
    head_type,
)
```

The AI should assemble these rather than generate every triangle itself.

---

# PHASE 17 — PROCEDURAL STRUCTURE GENERATORS

Create reusable high-level generators:

```text
inline_engine
v_engine
electric_motor
gearbox
turbine
motherboard
laptop
battery_pack
robot_arm
```

Example:

```json
{
  "generator": "v_engine",
  "parameters": {
    "cylinders": 8,
    "bank_angle": 90
  }
}
```

Generators produce semantic scene parts.

Do NOT hardcode them only for a demo.

---

# PHASE 18 — 3D RENDERER

Build a standalone Babylon.js + TypeScript renderer.

Preferred stack:

```text
Babylon.js
WebGPU
WebGL fallback
Vite
TypeScript
```

Renderer responsibilities:

- render loop
- camera
- meshes
- lighting
- materials
- labels
- mesh picking
- particles
- animation
- clipping planes
- X-ray
- exploded view
- progressive building
- quality management

Python must not render frames.

---

# PHASE 19 — RENDERER PROTOCOL

Connect Python to renderer using a localhost-only WebSocket.

Bind:

```text
127.0.0.1
```

Protocol:

```json
{
  "version": 1,
  "type": "part.add",
  "session_id": "abc",
  "sequence": 14,
  "payload": {}
}
```

Required commands:

```text
scene.create
scene.patch
scene.clear

part.add
part.update
part.remove
part.select
part.hide
part.show
part.materialize
part.dissolve
part.explode

camera.orbit
camera.pan
camera.zoom
camera.reset

view.explode
view.reassemble
view.xray
view.slice
view.reset

annotation.add
annotation.remove

renderer.ready
renderer.metrics
selection.changed
```

Handle:

- disconnect
- reconnect
- stale sequence
- duplicate sequence
- malformed command
- stale session

---

# PHASE 20 — SPATIAL SESSION

Maintain Python-side authoritative state:

```python
SpatialSession(
    session_id,
    scene,
    scene_revision,
    selected_part_ids,
    active_mode,
    camera_state,
    renderer_connected,
    undo_stack,
    redo_stack,
)
```

If renderer restarts:

```text
session survives
renderer reconnects
scene can be replayed
```

---

# PHASE 21 — LIVE PROGRESSIVE BUILDING

This is required.

When user says:

> Zaya, build a four-cylinder engine.

Do NOT:

```text
wait
wait
wait
show full model
```

Instead:

```text
prompt
↓
scene skeleton
↓
send first components
↓
renderer begins materialization
↓
planner continues
↓
more components stream in
```

Part state:

```text
PLANNED
QUEUED
SPAWNING
MATERIALIZING
READY
```

Example experience:

```text
0.2s → particles start appearing

0.5s → crankshaft/basic body visible

1.0s → pistons begin forming

1.5s → connecting rods

2.0s → engine block

3.0s → valves, screws, details
```

User must be able to rotate and zoom the partially built object while later components are still being generated.

---

# PHASE 22 — SAND ENGINE

Sand is a visual materialization system.

Do NOT turn semantic objects into meaningless particle clouds.

Each part still has a real mesh/node.

Materialization:

```text
target part known
↓
particle cloud spawned
↓
particles converge
↓
mesh progressively appears
↓
particles disappear
↓
semantic mesh remains
```

Dissolve:

```text
mesh
↓
particles emit
↓
mesh fades
↓
particles disperse
```

Rebuild reverses this.

Implement:

```text
materialize
dissolve
rebuild
highlight
explode
reassemble
```

Particle simulation belongs in renderer/GPU code.

Never create huge particle lists in Python.

---

# PHASE 23 — PERFORMANCE QUALITY

Adaptive particle quality:

```text
HIGH
MEDIUM
LOW
```

HIGH:

- full particles
- better effects
- shadows

MEDIUM:

- reduced particles
- lighter shadows

LOW:

- minimal materialization particles
- prioritize interaction

Measure renderer FPS.

If FPS drops for sustained periods:

```text
reduce visual quality automatically
```

Interaction responsiveness wins over visual beauty.

---

# PHASE 24 — MESH SELECTION

Every renderer mesh maps to:

```text
part_id
```

Use Babylon raycasting/picking.

Mouse:

```text
screen point
→ mesh
→ part_id
```

Hand:

```text
index fingertip
→ normalized screen coordinate
→ renderer raycast
→ mesh
→ part_id
```

Send:

```json
{
  "type": "selection.changed",
  "part_id": "piston_3"
}
```

Python stores this in SpatialSession.

---

# PHASE 25 — HAND-CONTROLLED 3D

Direct local controls:

## Open palm + movement

```text
orbit camera
```

## Two hands apart/together

```text
zoom
```

## Point

```text
hover object
```

## Index poke

```text
select object
```

## Pinch

```text
grab selected part
```

## Pinch + move

```text
translate selected part
```

## Pinch + wrist rotation

```text
rotate selected part
```

## Two-hand pull apart

```text
exploded view
```

## Fist

```text
cancel/release
```

These operations MUST NOT call the LLM.

---

# PHASE 26 — VOICE + HAND CONTEXT

When user selects:

```text
piston_3
```

then says:

> Zaya, what is this?

Zaya receives:

```text
spoken request
selected part ID
scene metadata
related parts
```

Do not guess what "this" means.

Commands must support:

> Explain this.

> Remove this.

> Pull this out.

> Make this transparent.

> What connects to this?

> Make this larger.

> Highlight everything connected to this.

> Show how this moves.

---

# PHASE 27 — EXPLODED VIEW

Each part stores an exploded displacement or generated explode vector.

Support:

```text
explode selected
explode group
explode layer
explode all
reassemble
```

Maintain original transforms.

Explode must be reversible.

---

# PHASE 28 — X-RAY

Support:

```text
normal
outer transparent
selected transparent
internal only
wireframe
```

Example:

> Make the outer casing transparent.

Once target is resolved, renderer executes locally.

---

# PHASE 29 — SLICE / CROSS SECTION

Support clipping planes:

```text
X
Y
Z
custom
```

Commands:

> Cut through the center.

> Move the slice left.

> Rotate the cutting plane.

No scene regeneration.

---

# PHASE 30 — AI SCENE PLANNER

The LLM outputs only validated structured scene descriptions.

Never arbitrary JavaScript.

Never arbitrary Babylon calls.

Never arbitrary Python code.

Scene planner chooses:

```text
procedural generator
component assembly
asset import
approximate scene
```

Output passes strict validation before being accepted.

---

# PHASE 31 — RESOURCE LIMITS

Hard limits are mandatory.

Start approximately with:

```text
max initial parts = 250
max graph depth = 12
max patch operations = 100
max annotations = 100
bounded particle budget
bounded command queue
```

Reject abusive model-generated values.

Do not let the LLM request:

```text
billions of particles
```

---

# PHASE 32 — SCENE PATCHING

Once an object exists, modify it via patches.

User:

> Make this piston 20% wider.

Do NOT regenerate engine.

Generate:

```json
{
  "operations": [
    {
      "op": "update",
      "part_id": "piston_3",
      "path": "geometry.radius",
      "value": 1.2
    }
  ]
}
```

Validate.

Apply.

Animate transition.

Keep undo/redo.

---

# PHASE 33 — LARGE STRUCTURAL MODIFICATIONS

User:

> Turn this four-cylinder engine into a V8.

Generate a larger patch plan:

```text
modify block
add second cylinder bank
add pistons
add connecting rods
modify crankshaft
modify heads
update relationships
```

Existing compatible parts remain.

New parts progressively materialize.

Do not blank the scene and recreate everything unless absolutely necessary.

---

# PHASE 34 — GLB / GLTF IMPORT

Support:

```text
.glb
.gltf
```

Preserve:

- hierarchy
- node names
- transforms
- metadata

If meaningful node names exist:

```text
Crankshaft
Piston_L1
Valve_03
```

map them into semantic parts.

Unknown objects stay unknown.

Do not invent names without confidence.

---

# PHASE 35 — CACHING

Cache semantic scenes.

Cache key based on normalized:

```text
object
generator
parameters
schema version
```

Example:

```text
four-cylinder inline engine
```

should load rapidly after first generation.

Cache semantic data separately from renderer state.

---

# PHASE 36 — CAMERA RESOURCE MANAGEMENT

Camera is not permanently active unless user enables it.

Settings:

```text
hand controls on/off
camera device
target FPS
mirror
gesture sensitivity
confidence threshold
debug landmarks
```

When disabled:

```text
camera closes
MediaPipe stops
workers stop
resources release
```

---

# PHASE 37 — PRIVACY

Camera processing local by default.

Do not:

- save raw frames
- upload continuous frames
- include them automatically in LLM prompts

Screen processing local by default.

Do not continuously upload desktop frames.

Only deeper AI vision receives images when explicitly necessary.

---

# PHASE 38 — THREADING

Use separate bounded workers for:

```text
Qt UI
camera capture
MediaPipe
screen perception
OCR
Zaya runtime
renderer
```

Never:

- block Qt
- run AI inside camera worker
- mutate Qt from background thread
- process a huge backlog of stale frames

For real-time video:

```text
newest frame wins
```

Dropping old frames is better than latency buildup.

---

# PHASE 39 — PERFORMANCE TARGETS

Aim for:

```text
renderer:
60 FPS target
30 FPS acceptable fallback
```

Gesture response:

```text
<80 ms target
```

Hand landmarks:

```text
20–30 useful updates/sec
```

Screen perception:

```text
10–15 FPS cheap processing
```

Procedural scene:

```text
first visible structure <500 ms target
```

Complex AI-built scene:

```text
first useful partial structure <2 sec target
```

Do not wait for full completion before rendering.

---

# PHASE 40 — FAILURE ISOLATION

Renderer crash:

```text
Zaya remains alive
```

Camera failure:

```text
voice/mouse still work
```

MediaPipe missing:

```text
only hand features disabled
```

WebGPU missing:

```text
WebGL fallback
```

Scene generation failure:

```text
existing scene untouched
```

Bad patch:

```text
reject patch
keep current scene
```

No optional subsystem can prevent normal Zaya startup.

---

# PHASE 41 — TESTS

Write deterministic tests.

## Hand tests

Synthetic landmarks for:

```text
open palm
index-only
point
pinch
poke
whole-hand movement
jitter
hand disappearance
hand reacquisition
```

## Keyboard critical test

Prove:

```text
open palm moves across Q W E R T Y
→ zero keys

index-only hover H
→ zero keys

poke H
→ exactly one H

remain forward
→ no second H

move while forward to J
→ no J

retract
→ unlock

poke J
→ exactly one J

move whole hand toward camera
→ zero keys

Z jitter around boundary
→ zero duplicates
```

## Scene graph

Test:

```text
unique IDs
valid parents
no cycles
valid geometry
valid relationships
bounded depth
```

## Patch engine

Test:

```text
update
add
remove
rollback
undo
redo
invalid IDs
invalid path
revision mismatch
```

## Protocol

Test:

```text
duplicate sequence
stale sequence
malformed message
reconnect
renderer restart
wrong session
```

---

# PHASE 42 — REQUIRED FINAL DEMOS

## DEMO 1

Virtual keyboard.

Open palm movement causes no typing.

Index-only + poke enters exactly one key.

No duplicate.

## DEMO 2

Say:

> Zaya, build a four-cylinder engine.

It starts appearing progressively.

Sand particles visibly construct each part.

## DEMO 3

While engine is still building:

- rotate it
- zoom it

Building must continue.

## DEMO 4

Point at piston.

Poke.

Piston selected.

Say:

> Explain this.

Zaya knows exact piston.

## DEMO 5

Pinch piston.

Move hand.

Piston moves.

Rotate wrist.

Piston rotates.

Release.

## DEMO 6

Say:

> Make the casing transparent.

X-ray effect occurs.

## DEMO 7

Say:

> Explode the engine.

Semantic components separate.

Say:

> Put it back.

They return.

## DEMO 8

Say:

> Cut it through the center.

Cross-section appears.

## DEMO 9

Say:

> Turn this into a V8.

Existing engine evolves.

New parts progressively materialize.

Do not simply clear the scene first.

## DEMO 10

Kill the renderer.

Zaya remains operational.

Restart renderer.

Scene restores/reconnects.

---

# IMPLEMENTATION ORDER

Follow this order:

```text
1. perception state
2. hand tracker
3. smoothing
4. gestures
5. keyboard state machine
6. virtual keyboard UI
7. ghost keyboard integration
8. overlay extension
9. spatial schemas
10. scene graph
11. spatial session
12. protocol
13. renderer
14. primitives
15. procedural components
16. template generators
17. progressive build
18. sand materialization
19. selection
20. hand spatial controls
21. voice + selection
22. explode
23. x-ray
24. slicing
25. scene planner
26. patch engine
27. cache
28. GLB/glTF
29. performance adaptation
30. production hardening
```

Do not jump directly to visual polish before interaction correctness.

---

# DEVELOPMENT RULES

Do not repeatedly inspect the repository.

Do not write lengthy plans before implementing.

You already have context.

Open only the files required for the current implementation step.

Implement incrementally.

For each phase:

```text
write focused test
implement
run test
fix
move forward
```

Do not stop after creating files.

Wire everything together.

Do not leave primary workflows as TODOs.

Do not fake successful actions.

Do not create duplicate systems where Zaya already has working infrastructure.

Preserve current features.

Do not delete unrelated behavior.

---

# DEFINITION OF DONE

The subsystem is complete only when Zaya can:

```text
SEE
→ continuous screen perception

TRACK
→ hand landmarks

UNDERSTAND GESTURES
→ deterministic gesture engine

TYPE
→ virtual keyboard

SELECT
→ point/poke 3D semantic parts

BUILD
→ generated 3D structures

MATERIALIZE
→ live sand construction

ROTATE
→ hand movement

ZOOM
→ two-hand gesture

GRAB
→ pinch

INSPECT
→ explode / X-ray / slice

UNDERSTAND "THIS"
→ selected semantic object context

MODIFY
→ natural-language scene patches

REBUILD
→ changed/new components progressively materialize
```

Normal Zaya must remain operational even if:

```text
camera fails
MediaPipe fails
renderer fails
WebGPU fails
spatial scene generation fails
```

Prioritize:

```text
correct interaction
→ low latency
→ architecture
→ reliability
→ visual quality
```

not the other way around.