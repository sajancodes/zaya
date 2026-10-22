export type RoadmapStatus = 'SHIPPED' | 'IN DEVELOPMENT' | 'EXPERIMENTAL' | 'PLANNED' | 'RESEARCH';

export interface RoadmapMilestone {
  id: string;
  quarter: string;
  title: string;
  status: RoadmapStatus;
  summary: string;
  details: string[];
  deliverables: string[];
}

export const ROADMAP_DATA: RoadmapMilestone[] = [
  {
    id: 'm1-voice-foundations',
    quarter: 'Phase 1 · Shipped',
    title: 'Gemini Live & Desktop Core',
    status: 'SHIPPED',
    summary: 'Direct low-latency bidirectional voice, Nika voice synthesis, acoustic interruption, and system audio ducking.',
    details: [
      'Bidirectional PCM16 streaming via WebSockets to Gemini Live.',
      'WebRTC VAD for microsecond barge-in interruption.',
      'System audio ducking to 20% on Windows CoreAudio during speech.',
      'Desktop presence companion with animated GIF/PNG expressions and poke responses.'
    ],
    deliverables: ['Live audio client', 'Companion HUD', 'Audio ducking filter']
  },
  {
    id: 'm2-operator-memory',
    quarter: 'Phase 2 · Shipped',
    title: 'Operating System Tools & Structured Memory',
    status: 'SHIPPED',
    summary: 'Full desktop control hierarchy, application lifecycle, Playwright browser automation, and SQLite FTS5 memory archive.',
    details: [
      'Multi-tiered execution: Native Control → Browser DOM → UIA → Set-of-Mark → Vision → Coordinates.',
      'Windows DPAPI encryption for local API keys and credentials.',
      'Full Access security gate with prompt confirmation for destructive actions.',
      'Local conversation archive with max-5 message on-demand semantic recall.'
    ],
    deliverables: ['Operator core', 'Playwright driver', 'SQLite knowledge base']
  },
  {
    id: 'm3-android-whatsapp',
    quarter: 'Phase 3 · Shipped',
    title: 'Android Companion & WhatsApp Bridge',
    status: 'SHIPPED',
    summary: 'Native Kotlin/Jetpack Compose Android companion, Zaya-initiated phone calls, live video context, and Hermes WhatsApp link.',
    details: [
      'Native Android companion mirroring companion state and task lists.',
      'Zaya-initiated phone calls (P0/P1 ringing, P2 notification, P3 silent).',
      'Opt-in phone video streaming for real-time mobile visual reasoning.',
      'Hermes WhatsApp bridge supporting Observe, Draft, and Auto modes.'
    ],
    deliverables: ['Android app release', 'Hermes linked-session manager', 'Video stream receiver']
  },
  {
    id: 'm4-spatial-hands',
    quarter: 'Phase 4 · Shipped / Beta',
    title: 'Optical Hand Control & Spatial 3D Workspace',
    status: 'SHIPPED',
    summary: 'MediaPipe 21-joint optical hand tracking, depth-invariant air keyboard, and interactive Babylon.js 3D spatial workspace.',
    details: [
      'Isolated MediaPipe Hand Landmarker child worker (.venv-hands) at 30 FPS.',
      'Adaptive air keyboard with palm-scale depth normalization and debouncing.',
      'Babylon.js WebGPU/WebGL 3D spatial canvas with GLB/glTF streaming.',
      'Exploded assemblies, X-ray view, semantic labeling, and natural language spatial planner.'
    ],
    deliverables: ['ZayaHandWorker', 'Spatial WebGPU Canvas', 'Air Keyboard overlay']
  },
  {
    id: 'm5-supervised-coding',
    quarter: 'Phase 5 · In Development',
    title: 'Autonomous Coding Supervisor & Mission Engine',
    status: 'IN DEVELOPMENT',
    summary: 'Multi-pass coding supervisor running OpenCode CLI with tool-free review, test isolation, and durable 10-state missions.',
    details: [
      'Owner task compilation into structured briefs with verification criteria.',
      'Supervised OpenCode CLI execution with real-time progress narration.',
      'Automated test suite execution and git diff boundary tracking.',
      'Strict three-pass follow-up ceiling preventing infinite prompt loops.'
    ],
    deliverables: ['OpenCode supervisor', 'Mission durable state machine', 'Test runner']
  },
  {
    id: 'm6-offline-perception',
    quarter: 'Phase 6 · In Development',
    title: 'Zero-Cloud Continuous Perception 2.0',
    status: 'IN DEVELOPMENT',
    summary: 'Neural on-device scene segmentation, local OCR streaming, and proactive anomaly alerts without cloud bandwidth.',
    details: [
      'Ultra-fast differential frame hashing (mss + OpenCV) sub-5ms.',
      'Windows native in-memory OCR streaming directly through stdin without disk writes.',
      'Contextual awareness: detects compile errors, broken downloads, and long-running job finishes.'
    ],
    deliverables: ['Continuous perception engine', 'Local anomaly detector']
  },
  {
    id: 'm7-multi-device-mesh',
    quarter: 'Phase 7 · Experimental',
    title: 'Cross-Device Neural Mesh & Spatial Relaying',
    status: 'EXPERIMENTAL',
    summary: 'Peer-to-peer authenticated synchronization across multiple workstations, tablets, and spatial displays.',
    details: [
      'Encrypted local LAN discovery via mDNS with zero cloud broker.',
      'Seamless desktop handoff: move active missions and 3D scenes between laptops.',
      'Stereoscopic spatial rendering for XR headsets (WebXR).'
    ],
    deliverables: ['LAN Mesh Protocol', 'WebXR Spatial Renderer']
  },
  {
    id: 'm8-agentic-ecosystem',
    quarter: 'Phase 8 · Planned',
    title: 'Decentralized Tool Ecosystem & Self-Hosting',
    status: 'PLANNED',
    summary: 'Sandboxed custom action plugins, community tool registry, and one-click self-hosted private cloud relay.',
    details: [
      'Wasm-sandboxed action runtimes for untrusted plugin execution.',
      'Owner-signed community tool repository.',
      'Self-hosted relay server for remote phone access without port forwarding.'
    ],
    deliverables: ['Wasm plugin runtime', 'Zaya Cloud Relay']
  },
  {
    id: 'm9-embodied-intelligence',
    quarter: 'Phase 9 · Research',
    title: 'Embodied Spatial Perception & World Models',
    status: 'RESEARCH',
    summary: 'Long-term research into 3D Gaussian splatting, continuous spatial memory, and physical robotic actuation.',
    details: [
      'Reconstructing room-scale 3D workspaces from phone camera sweeps.',
      'Persistent spatial anchors for virtual objects in physical rooms.',
      'Unified multimodal physical reasoning.'
    ],
    deliverables: ['Gaussian Splat Pipeline', 'Spatial Anchor Store']
  }
];
