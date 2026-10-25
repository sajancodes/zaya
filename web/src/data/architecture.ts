export interface SystemNode {
  id: string;
  name: string;
  layer: 'INPUT' | 'CORE' | 'AI' | 'TOOLS' | 'OUTPUT';
  summary: string;
  description: string;
  keyFiles: string[];
  techStack: string[];
  protocols: string[];
}

export const ARCHITECTURE_LAYERS = [
  { id: 'INPUT', name: 'Input & Sensor Peripherals', color: '#49DFFF' },
  { id: 'CORE', name: 'Zaya Core Intelligence & Policy', color: '#3478FF' },
  { id: 'AI', name: 'Multimodal AI & Speech Engine', color: '#A855F7' },
  { id: 'TOOLS', name: 'Operating System Tools & Actuators', color: '#10B981' },
  { id: 'OUTPUT', name: 'Output Displays & Relays', color: '#00D4FF' },
] as const;

export const ARCHITECTURE_NODES: SystemNode[] = [
  // INPUT
  {
    id: 'input-voice',
    name: 'Voice & Microphone',
    layer: 'INPUT',
    summary: 'Hardware microphone capture with WebRTC VAD gating and acoustic interruption.',
    description: 'Captures 16kHz/24kHz PCM audio streams, applies real-time voice activity detection, and detects owner interruptions to stop synthesis instantly.',
    keyFiles: ['core/speech/vad.py', 'core/audio_pipeline.py', 'core/echo.py'],
    techStack: ['PyAudio', 'WebRTC VAD', 'PortAudio'],
    protocols: ['PCM16', 'Direct Sound / CoreAudio']
  },
  {
    id: 'input-text',
    name: 'Text & Shortcuts',
    layer: 'INPUT',
    summary: 'Desktop controls window, push-to-talk chords, and global hotkeys.',
    description: 'Captures typed queries, system tray shortcuts, and hardware push-to-talk buttons with zero lag and zero input telemetry.',
    keyFiles: ['core/hotkey.py', 'ui.py', 'core/task_runtime.py'],
    techStack: ['PySide6 / Tkinter', 'Windows User32 API'],
    protocols: ['Win32 Hotkey Hook', 'Async Queue']
  },
  {
    id: 'input-phone',
    name: 'Android Phone Bridge',
    layer: 'INPUT',
    summary: 'Encrypted mobile pairing relaying commands, audio, and camera frames.',
    description: 'Receives authenticated voice packets, remote goal submissions, and live camera context from the native Android app.',
    keyFiles: ['core/mobile_bridge.py', 'core/mobile_protocol.py'],
    techStack: ['Kotlin', 'Android Jetpack Compose', 'Python WebSockets'],
    protocols: ['Encrypted WSS', 'H.264 / WebRTC']
  },
  {
    id: 'input-whatsapp',
    name: 'WhatsApp Incoming Feed',
    layer: 'INPUT',
    summary: 'Multi-device Hermes session monitoring incoming contact conversations.',
    description: 'Observes incoming chats, classifies message urgency, and surfaces voice announcements without exposing chat logs to public servers.',
    keyFiles: ['services/whatsapp/inbox.py', 'services/whatsapp/gateway.py'],
    techStack: ['Hermes Gateway', 'Node.js', 'SQLite'],
    protocols: ['Baileys WA Protocol', 'JSON IPC']
  },
  {
    id: 'input-screen',
    name: 'Screen Perception',
    layer: 'INPUT',
    summary: 'Differential frame capture, active window titles, and bounded in-memory OCR.',
    description: 'Continuously hashes desktop display frames locally. Changes trigger bounding-box diffs and in-memory OCR without writing files to disk.',
    keyFiles: ['core/perception/', 'actions/display_perception.py'],
    techStack: ['mss', 'OpenCV Contrib', 'Windows Media OCR'],
    protocols: ['Direct Frame Buffer', 'WinRT OCR']
  },
  {
    id: 'input-hand',
    name: 'Optical Hand Sensor',
    layer: 'INPUT',
    summary: 'Webcam-based 21-landmark 3D skeleton inference via isolated worker.',
    description: 'Streams camera frames into ZayaHandWorker running Google MediaPipe. Detects open palms, pokes, pinches, and fists at 30 FPS.',
    keyFiles: ['core/gesture/', 'actions/hand_controls.py'],
    techStack: ['MediaPipe 0.10', 'OpenCV', 'Subprocess Worker'],
    protocols: ['Shared Memory / IPC Pipe', 'JSON-Lines']
  },

  // CORE
  {
    id: 'core-policy',
    name: 'Trust Boundary & Policy',
    layer: 'CORE',
    summary: 'Strict authority enforcement: External data is DATA, NOT AUTHORITY.',
    description: 'Ensures external web content, incoming messages, and perception text cannot invoke destructive actions without explicit owner confirmation.',
    keyFiles: ['core/security/execution_policy.py', 'core/confirm.py'],
    techStack: ['Python', 'Windows DPAPI', 'Crypto32'],
    protocols: ['Owner Confirmation Gate', 'Token Auth']
  },
  {
    id: 'core-router',
    name: 'Universal Tool Router',
    layer: 'CORE',
    summary: 'Intent parsing, tool discovery, and execution dispatcher.',
    description: 'Routes conversational instructions to native tools, Playwright automation, shell commands, or spatial planners with schema validation.',
    keyFiles: ['core/universal_router.py', 'core/live_tools.py'],
    techStack: ['Pydantic', 'Python Type Annotations'],
    protocols: ['JSON-Schema Tool Call', 'ToolResult']
  },
  {
    id: 'core-memory',
    name: 'Memory & Knowledge Store',
    layer: 'CORE',
    summary: 'Local conversation archive, BM25 FTS5 search, and long-term facts.',
    description: 'Preserves private chat history in conversation.db. Fresh sessions load clean with zero preloading, querying at most 5 messages when asked.',
    keyFiles: ['memory/conversation.db', 'memory/store.py', 'core/workspace_context.py'],
    techStack: ['SQLite3', 'FTS5 Full-Text Engine'],
    protocols: ['SQL Local Queries', 'BM25 Ranking']
  },
  {
    id: 'core-missions',
    name: 'Mission Supervisor',
    layer: 'CORE',
    summary: '10-state durable execution engine with bounded retries and crash recovery.',
    description: 'Tracks long-running workflows across restarts. Persists task evidence, inspects return codes, and pauses gracefully on unexpected blockers.',
    keyFiles: ['core/mission_supervisor.py', 'core/task_runtime.py'],
    techStack: ['SQLite', 'Asyncio Task Trees'],
    protocols: ['Mission Event Stream', 'NDJSON State']
  },

  // AI ENGINE
  {
    id: 'ai-gemini-live',
    name: 'Gemini Live Client',
    layer: 'AI',
    summary: 'Bidirectional full-duplex voice WebSocket to Google Gemini 3.8 Live.',
    description: 'Transfers live PCM16 audio blocks and receives streaming audio and tool call declarations with sub-second response times.',
    keyFiles: ['core/gemini.py', 'core/gemini_keys.py'],
    techStack: ['Google GenAI SDK', 'WebSockets', 'AsyncIO'],
    protocols: ['Bidi WebSockets', 'Protobuf / JSON']
  },
  {
    id: 'ai-local-modular',
    name: 'Modular Local AI Pipeline',
    layer: 'AI',
    summary: 'Split-engine: faster-whisper STT → Local LLM → Piper ONNX TTS.',
    description: 'Completely offline voice and reasoning loop connecting to Ollama, LM Studio, or llama.cpp with zero external network dependencies.',
    keyFiles: ['core/speech/whisper.py', 'core/llm/local_runner.py', 'core/speech/piper.py'],
    techStack: ['faster-whisper', 'Piper TTS', 'Ollama / llama.cpp'],
    protocols: ['OpenAI /v1/chat/completions', 'ONNX Runtime']
  },

  // TOOLS
  {
    id: 'tools-computer',
    name: 'Desktop & UIA Operator',
    layer: 'TOOLS',
    summary: 'Native Win32 control, UI Automation, Set-of-Mark, and coordinate fallback.',
    description: 'Operates Windows controls by programmatic element inspection, window handles, accessibility trees, and verified keystroke injection.',
    keyFiles: ['actions/computer_control.py', 'core/operator.py'],
    techStack: ['pywinauto', 'Windows UIA', 'SendInput'],
    protocols: ['Win32 Messaging', 'UIAutomation COM']
  },
  {
    id: 'tools-browser',
    name: 'Playwright Browser Automation',
    layer: 'TOOLS',
    summary: 'Isolated persistent browser contexts with login-state recovery.',
    description: 'Automates complex multi-step web workflows, form interaction, data extraction, and destination URL verification.',
    keyFiles: ['actions/browser_control.py'],
    techStack: ['Playwright', 'Chromium / Firefox'],
    protocols: ['Chrome DevTools Protocol (CDP)']
  },
  {
    id: 'tools-coding',
    name: 'OpenCode Coding Supervisor',
    layer: 'TOOLS',
    summary: 'Orchestrates OpenCode CLI processes, git diff tracking, and test execution.',
    description: 'Compiles tasks into briefs, manages code changes, runs tests, and conducts bounded reviews with up to 3 automated follow-up passes.',
    keyFiles: ['core/coding_supervisor.py', 'actions/coding_job.py', 'core/opencode_cli.py'],
    techStack: ['OpenCode CLI', 'Git', 'Subprocess PTY'],
    protocols: ['JSON Event Stream', 'Process Tree IPC']
  },

  // OUTPUT
  {
    id: 'output-companion',
    name: 'Desktop Taskbar Companion',
    layer: 'OUTPUT',
    summary: 'Animated transparent overlay with emotional expressions and comic speech bubbles.',
    description: 'Renders Nika expressions (neutral, happy, thinking, poked) and text bubbles directly above the Windows taskbar.',
    keyFiles: ['services/zayabar.py', 'services/companion_bubble.py', 'zayabar.json'],
    techStack: ['PySide6 / PyQt', 'Win32 WS_EX_LAYERED'],
    protocols: ['Native OS Compositor']
  },
  {
    id: 'output-spatial',
    name: 'Spatial 3D Workspace',
    layer: 'OUTPUT',
    summary: 'High-performance WebGPU/WebGL 3D canvas with progressive geometry streaming.',
    description: 'Renders exploded assemblies, X-ray models, and CAD schematics with optical hand manipulation and natural language AI planning.',
    keyFiles: ['spatial_renderer/', 'services/spatial_server.py'],
    techStack: ['Babylon.js', 'Vite', 'TypeScript', 'WebGPU / WebGL'],
    protocols: ['Local WebSocket Stream', 'GLB/glTF Binary']
  },
  {
    id: 'output-phone',
    name: 'Android Companion Output',
    layer: 'OUTPUT',
    summary: 'Synchronized mobile state, push alerts, voice, and audio route handover.',
    description: 'Directs audio speech to phone speakers during incoming calls, syncs task updates, and delivers missed-call summaries.',
    keyFiles: ['core/mobile_calls.py', 'core/mobile_bridge.py'],
    techStack: ['Android Telecom', 'WebSocket Client'],
    protocols: ['PCM16 Audio Relay', 'WSS State Push']
  }
];
