export type FeatureStatus = 'STABLE' | 'BETA' | 'EXPERIMENTAL' | 'PLANNED';
export type FeaturePlatform = 'WINDOWS' | 'ANDROID' | 'CROSS PLATFORM';
export type FeaturePrivacy = 'LOCAL' | 'CLOUD' | 'OPTIONAL CLOUD';

export interface FeatureItem {
  id: string;
  name: string;
  category: string;
  shortDescription: string;
  detailedDescription: string;
  status: FeatureStatus;
  platform: FeaturePlatform;
  privacy: FeaturePrivacy;
  dependencies: string[];
  docsLink?: string;
  highlights?: string[];
}

export const FEATURE_CATEGORIES = [
  'All',
  'Voice',
  'AI Engine',
  'Computer',
  'Browser',
  'Vision',
  'Perception',
  'Files',
  'Terminal',
  'Git',
  'Coding',
  'Missions',
  'Tasks',
  'Memory',
  'Hand Control',
  'Virtual Keyboard',
  'Spatial',
  'WhatsApp',
  'Android',
  'Calls',
  'Phone Video',
  'Media',
  'Audio',
  'Plugins',
  'Security',
  'Remote Control',
  'Distribution',
  'Updates'
] as const;

export const FEATURES: FeatureItem[] = [
  // VOICE
  {
    id: 'voice-gemini-live',
    name: 'Gemini Live Bidirectional Voice',
    category: 'Voice',
    shortDescription: 'Full-duplex conversational voice streaming over WebSockets with real-time speech synthesis.',
    detailedDescription: 'Streams microphone and response audio through the configured Gemini Live model for conversational voice. Response time depends on the provider and network.',
    status: 'STABLE',
    platform: 'CROSS PLATFORM',
    privacy: 'CLOUD',
    dependencies: ['Gemini API Key', 'Microphone', 'Audio Output'],
    docsLink: '/docs/voice',
    highlights: ['Bidirectional audio streaming', 'Configurable voice settings', 'Conversational turns']
  },
  {
    id: 'voice-speech-interruption',
    name: 'Barge-In & Acoustic Interruption',
    category: 'Voice',
    shortDescription: 'Speak at any point during Zaya’s response to immediately halt queued speech and pivot.',
    detailedDescription: 'Local WebRTC VAD and energy-based speech detection catches owner speech during output playback, truncates speech buffers, and resumes active listening instantly.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['PyAudio', 'WebRTC VAD'],
    docsLink: '/docs/voice',
    highlights: ['Zero latency cutoff', 'Acoustic echo suppression', 'No provider round-trip needed']
  },
  {
    id: 'voice-wake-word',
    name: 'Local Wake-Word Gating & Push-to-Talk',
    category: 'Voice',
    shortDescription: 'Private on-device acoustic keyword spotting or hardware hotkey trigger.',
    detailedDescription: 'Keeps audio stream offline until the trained wake phrase or physical push-to-talk hotkey is held, preventing unintended ambient listening.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['Local Hotkey Hook', 'OpenWakeWord Engine'],
    docsLink: '/docs/voice'
  },
  {
    id: 'voice-ducking',
    name: 'System Audio Ducking',
    category: 'Audio',
    shortDescription: 'Automatically attenuates background desktop sound during active speech.',
    detailedDescription: 'Windows CoreAudio session mixer drops background application audio to 20% when either owner or Zaya speaks, smoothly ramping back to full volume after release.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['Windows CoreAudio / pycaw'],
    docsLink: '/docs/voice'
  },

  // AI ENGINE
  {
    id: 'ai-modular-engine',
    name: 'Modular Local AI Engine',
    category: 'AI Engine',
    shortDescription: 'Split-pipeline local intelligence replacing cloud services with on-device models.',
    detailedDescription: 'Combines local WebRTC VAD, faster-whisper speech transcription, local LLM inference via Ollama / LM Studio / llama.cpp, and onnx Piper voice synthesis.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['faster-whisper', 'Piper ONNX', 'Local LLM (Ollama/llama.cpp)'],
    docsLink: '/docs/local-ai'
  },
  {
    id: 'ai-provider-failover',
    name: 'Multi-Key & Multi-Provider Failover',
    category: 'AI Engine',
    shortDescription: 'Automatic rate-limit recovery and multi-key rotation on 429 quota exhaustion.',
    detailedDescription: 'Maintains prioritized key rotation pools and provider fallbacks. When Gemini hits quota limits, Zaya seamlessly shifts to alternate keys or secondary providers without dropping conversation state.',
    status: 'STABLE',
    platform: 'CROSS PLATFORM',
    privacy: 'OPTIONAL CLOUD',
    dependencies: ['Configured Keys in api_keys.json'],
    docsLink: '/docs/providers'
  },

  // COMPUTER CONTROL
  {
    id: 'computer-operator',
    name: 'Hierarchical Computer Operator',
    category: 'Computer',
    shortDescription: 'Multi-tiered desktop manipulation following an Observe → Identify → Act → Verify paradigm.',
    detailedDescription: 'Tiered execution engine attempting Native Control first, followed by Browser DOM, Windows UI Automation (UIA), Set-of-Mark visual tagging, vision segmentation, and precise coordinate fallback.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['Windows UI Automation', 'PyAutoGUI / SendInput'],
    docsLink: '/docs/computer-control',
    highlights: ['Never clicks blind coordinates', 'Post-action verification check', 'Atomic action rollback on failure']
  },
  {
    id: 'computer-app-management',
    name: 'Application & Window Lifecycle',
    category: 'Computer',
    shortDescription: 'Open, minimize, focus, tile, and gracefully terminate desktop software.',
    detailedDescription: 'Direct Windows process and ShellExecute integration with title matching, multi-monitor coordinates, and process tree tree-kill safeguards.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['win32gui', 'psutil'],
    docsLink: '/docs/computer-control'
  },

  // BROWSER
  {
    id: 'browser-hybrid',
    name: 'Hybrid Browser Automation & Recovery',
    category: 'Browser',
    shortDescription: 'Native browser launching alongside deep Playwright DOM automation.',
    detailedDescription: 'Launches your standard browser (Brave, Chrome, Firefox) for daily links, and creates isolated persistent Playwright contexts for deep programmatic navigation, form completion, and content extraction.',
    status: 'STABLE',
    platform: 'CROSS PLATFORM',
    privacy: 'LOCAL',
    dependencies: ['Playwright Chromium / Firefox'],
    docsLink: '/docs/browser'
  },

  // VISION & PERCEPTION
  {
    id: 'vision-continuous-perception',
    name: 'Continuous Local Screen Perception',
    category: 'Perception',
    shortDescription: 'Zero-cloud screen awareness monitoring active applications and UI region changes.',
    detailedDescription: 'Performs differential frame hashing, bounding-box motion tracking, and active window inspection locally at low CPU overhead. No live video stream is ever transmitted to cloud providers.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['mss', 'OpenCV Contrib'],
    docsLink: '/docs/perception',
    highlights: ['Completely private on-device', 'Diff-based low overhead', 'Selective OCR streaming']
  },
  {
    id: 'vision-on-demand',
    name: 'On-Demand Visual Reasoning',
    category: 'Vision',
    shortDescription: 'High-resolution desktop or webcam snapshot analysis for contextual reasoning.',
    detailedDescription: 'Captures targeted window or desktop regions only when explicitly requested by user commands, analyzing UI layout, error popups, code snippets, or architectural diagrams.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'OPTIONAL CLOUD',
    dependencies: ['Desktop Capture', 'Multimodal LLM / Gemini Vision'],
    docsLink: '/docs/vision'
  },

  // CODING & DEV
  {
    id: 'coding-opencode-supervisor',
    name: 'Supervised OpenCode Orchestrator',
    category: 'Coding',
    shortDescription: 'Multi-pass coding assistant with structured briefs, tool-free review, and independent test verification.',
    detailedDescription: 'Compiles owner tasks into technical briefs, manages hidden OpenCode CLI worker processes, tracks git diffs, executes test suites, and enforces a strict three-pass correction ceiling.',
    status: 'STABLE',
    platform: 'CROSS PLATFORM',
    privacy: 'LOCAL',
    dependencies: ['OpenCode CLI', 'Git', 'Python / Node'],
    docsLink: '/docs/coding'
  },
  {
    id: 'git-automation',
    name: 'Verified Git Workflow Controller',
    category: 'Git',
    shortDescription: 'Repository inspection, branch creation, commit signing, and verified push operations.',
    detailedDescription: 'Validates repository clean states, diff boundaries, author identity checks (sajancodes), and runs status checks before executing pushes to origin.',
    status: 'STABLE',
    platform: 'CROSS PLATFORM',
    privacy: 'LOCAL',
    dependencies: ['Git CLI'],
    docsLink: '/docs/coding'
  },

  // AUTONOMY & MISSIONS
  {
    id: 'mission-supervisor',
    name: 'Mission Supervisor & Durable State Engine',
    category: 'Missions',
    shortDescription: 'Long-running autonomous execution with bounded retries, proof-of-work, and restart recovery.',
    detailedDescription: 'Orchestrates complex multi-step user goals through an explicit 10-state state machine: planning, running, waiting confirmation, waiting clarification, waiting external, paused, interrupted, completed, completed unverified, failed, cancelled.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['SQLite Mission Store'],
    docsLink: '/docs/missions'
  },

  // MEMORY
  {
    id: 'memory-structured-knowledge',
    name: 'Structured SQLite & FTS5 Knowledge Store',
    category: 'Memory',
    shortDescription: 'Continuous local conversation archive with semantic BM25 indexing and alias resolution.',
    detailedDescription: 'Stores private dialogue history in conversation.db. Fresh sessions start clean with zero context bloat; recalls at most five relevant messages on demand via indexed SQLite FTS5 queries.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['SQLite3 with FTS5'],
    docsLink: '/docs/memory'
  },

  // HAND CONTROL & VIRTUAL KEYBOARD
  {
    id: 'hand-optical-tracking',
    name: 'Optical Hand Landmark Tracking',
    category: 'Hand Control',
    shortDescription: 'Real-time 21-joint 3D hand skeleton inference running in an isolated sub-process.',
    detailedDescription: 'Uses Google MediaPipe Hand Landmarker model in an isolated process (.venv-hands) running at 30 FPS. Evaluates gestures: open palm (cursor), index poke (click), two fingers (selection), fist (scroll), thumbs up (Enter).',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['MediaPipe 0.10', 'OpenCV', 'Webcam'],
    docsLink: '/docs/hand-control'
  },
  {
    id: 'air-keyboard',
    name: 'Depth-Invariant Air Keyboard',
    category: 'Virtual Keyboard',
    shortDescription: 'Floating mid-air typing interface with palm-relative depth adaptation and debouncing.',
    detailedDescription: 'Projects a translucent cyan keyboard plane. Automatically normalizes keystroke depth based on hand scale from the camera, enforcing single-strike latching and refusing to inject keystrokes into credential windows.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['Ghost Keyboard Engine', 'SendInput'],
    docsLink: '/docs/air-keyboard'
  },

  // SPATIAL INTELLIGENCE
  {
    id: 'spatial-workspace-3d',
    name: '3D Spatial Intelligence & CAD Workspace',
    category: 'Spatial',
    shortDescription: 'Interactive WebGPU/WebGL 3D environment with GLB/glTF streaming and natural language planning.',
    detailedDescription: 'Babylon.js powered spatial canvas supporting progressive geometry streaming, exploded component views, X-ray inspection, semantic part labeling, and natural language scene transformations.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['Babylon.js', 'Vite / WebGPU / WebGL'],
    docsLink: '/docs/spatial'
  },

  // WHATSAPP
  {
    id: 'whatsapp-hermes-bridge',
    name: 'WhatsApp Hermes Linked Gateway',
    category: 'WhatsApp',
    shortDescription: 'Persistent multi-device WhatsApp link supporting Observe, Draft, and Auto modes.',
    detailedDescription: 'Maintains a linked-device WhatsApp session via Hermes bridge. Supports per-contact mode assignment, urgent vocal escalation, and strict activity privacy boundaries (shares current song/task, never private chat history).',
    status: 'STABLE',
    platform: 'CROSS PLATFORM',
    privacy: 'LOCAL',
    dependencies: ['Hermes Gateway', 'Node.js'],
    docsLink: '/docs/whatsapp'
  },

  // ANDROID COMPANION
  {
    id: 'android-companion-app',
    name: 'Native Android Companion (Kotlin / Jetpack Compose)',
    category: 'Android',
    shortDescription: 'A mobile connection to your laptop’s running Zaya instance.',
    detailedDescription: 'Native Kotlin app mirroring the companion state, live transcripts, active mission progress, WhatsApp messages, and file exchange over an encrypted local WebSocket bridge.',
    status: 'STABLE',
    platform: 'ANDROID',
    privacy: 'LOCAL',
    dependencies: ['Android 10+ (API 29+)', 'Encrypted Keystore'],
    docsLink: '/docs/mobile'
  },
  {
    id: 'android-calls-video',
    name: 'Zaya-Initiated Calls & Live Video Context',
    category: 'Calls',
    shortDescription: 'Incoming phone rings for urgent owner alerts and opt-in camera sharing.',
    detailedDescription: 'Zaya can proactively place priority calls to the owner phone for urgent alerts or completed tasks. During an active call, camera frames stream to the laptop for spatial visual reasoning.',
    status: 'STABLE',
    platform: 'ANDROID',
    privacy: 'LOCAL',
    dependencies: ['Camera2 API', 'Android Telecom Framework'],
    docsLink: '/docs/mobile'
  },

  // SECURITY & PRIVACY
  {
    id: 'security-trust-boundary',
    name: 'Owner Trust Boundary & ToolResult Architecture',
    category: 'Security',
    shortDescription: 'Owner-only authority model treating external content as untrusted data.',
    detailedDescription: 'Strict privilege isolation: Web content, OCR text, WhatsApp messages, and tool outputs are strictly classified as DATA, NOT AUTHORITY. Destructive operations require on-screen owner confirmation.',
    status: 'STABLE',
    platform: 'CROSS PLATFORM',
    privacy: 'LOCAL',
    dependencies: ['Windows DPAPI', 'ExecutionPolicy'],
    docsLink: '/docs/security'
  },
  {
    id: 'security-dpapi-storage',
    name: 'Windows DPAPI Encrypted Vault',
    category: 'Security',
    shortDescription: 'Windows user-account encryption for stored provider credentials.',
    detailedDescription: 'Uses Windows CryptProtectData to protect stored provider credentials under the Windows user account. This does not protect against a compromised, signed-in user session.',
    status: 'STABLE',
    platform: 'WINDOWS',
    privacy: 'LOCAL',
    dependencies: ['Windows Crypt32'],
    docsLink: '/docs/security'
  },
  // Additional tools are documented as beta capabilities, not certified release flows.
  ...([
    ['files-management', 'File & Folder Management', 'Files', 'Find, read, create, move and organize local files and folders with owner-controlled actions.', 'Filesystem access', '/docs/reference'],
    ['files-documents', 'Document Reading & Generation', 'Files', 'Work with supported documents and generate files for your tasks. Format support depends on installed libraries.', 'Document libraries', '/docs/reference'],
    ['terminal-owner-shell', 'Owner-Controlled Terminal', 'Terminal', 'Run terminal tasks in a working directory with the real execution policy and confirmation gate.', 'System shell', '/docs/security'],
    ['tasks-reminders', 'Reminders & Scheduled Calls', 'Tasks', 'Schedule reminders and request a phone call at a specified time. Phone delivery needs a paired, reachable device.', 'Reminder scheduler; Android pairing for calls', '/docs/reference'],
    ['tasks-calendar', 'Calendar & Meeting Scheduling', 'Tasks', 'Query schedules and create or reschedule meetings through the configured calendar integration.', 'Calendar connection', '/docs/reference'],
    ['tasks-background', 'Background Task Monitoring', 'Tasks', 'Follow ongoing work and inspect runtime status, progress and failures.', 'Running desktop session', '/docs/missions'],
    ['media-playback', 'Desktop Music & Media Controls', 'Media', 'Control playback, track changes, mute and volume through Windows media controls.', 'Compatible media player; Windows', '/docs/reference'],
    ['media-video', 'Video & YouTube Playback', 'Media', 'Open videos and work with supported playback controls using your desktop and browser.', 'Browser or supported player', '/docs/reference'],
    ['phone-camera-context', 'Opt-In Phone Camera Context', 'Phone Video', 'Share phone camera frames during a call for visual context. Quality and latency depend on the device and connection.', 'Paired Android companion; camera permission', '/docs/mobile'],
    ['phone-contacts', 'Phone Contacts & Call Actions', 'Remote Control', 'Look up contacts and request supported calling actions on your paired phone.', 'Android permissions; paired companion', '/docs/mobile'],
    ['phone-notifications', 'Phone Notifications & SMS', 'Remote Control', 'Access supported phone notifications and messaging actions after granting the required Android permissions.', 'Notification access or SMS permissions', '/docs/mobile'],
    ['phone-device-controls', 'Phone Device & App Controls', 'Remote Control', 'Request supported app launches, media actions, flashlight controls and device status from your laptop.', 'Paired Android companion; device permissions', '/docs/mobile'],
    ['phone-screen-context', 'Phone Screen Sharing', 'Remote Control', 'Share a phone screen capture for visual assistance with explicit Android screen-capture consent.', 'MediaProjection consent; vision provider', '/docs/mobile'],
    ['phone-owner-presence', 'Away & Presence Preferences', 'Calls', 'Tell Zaya when you are going out or back so phone-call delivery can use your stated availability.', 'Owner session; paired phone for delivery', '/docs/mobile'],
    ['plugins-extensions', 'Plugin & Tool Extensions', 'Plugins', 'Extend the desktop through configured plugins and discovered action tools. Additional integrations need their own setup.', 'Plugin configuration', '/docs/reference'],
    ['desktop-widgets', 'Floating Desktop Widgets', 'Computer', 'Create small desktop tools such as clocks, timers and calculators using Widget Forge.', 'Widget runtime', '/docs/reference'],
    ['desktop-customization', 'Companion Expressions & Controls', 'Computer', 'Use the taskbar character, expressions and Settings & Controls to personalize the desktop experience.', 'Desktop companion', '/docs/getting-started'],
    ['desktop-diagnostics', 'Runtime Logs & System Diagnostics', 'Computer', 'Inspect local runtime logs, resource information and diagnostic status when something needs attention.', 'Local desktop session', '/docs/troubleshooting'],
    ['web-research', 'Web Search & Research', 'Browser', 'Search the web and gather context through configured search and browser tools.', 'Internet connection; configured providers', '/docs/browser'],
    ['web-weather', 'Weather Reports', 'Browser', 'Request weather information through the configured weather tool.', 'Internet connection; weather service', '/docs/reference'],
    ['web-flight-search', 'Flight Search Assistance', 'Browser', 'Look for flight options through the flight-finder integration. Availability depends on its configured services.', 'Internet connection; flight search integration', '/docs/reference'],
    ['memory-profile', 'Personal Profile & Preferences', 'Memory', 'Save supported personal preferences and profile information for your assistant.', 'Local profile store', '/docs/memory'],
    ['memory-history', 'On-Demand Conversation History', 'Memory', 'Browse local conversation archives and request targeted recall without loading a previous session on startup.', 'Local conversation archive', '/docs/memory'],
    ['desktop-selected-text', 'Selected Text Assistance', 'Computer', 'Read selected text and use it as context for your current request.', 'Accessible selected text', '/docs/reference'],
    ['desktop-content-panels', 'Floating Content & Ghost Overlays', 'Computer', 'Display supported content and helper overlays alongside your desktop work.', 'Desktop display runtime', '/docs/reference'],
    ['audio-clap-toggle', 'Double-Clap Toggle', 'Audio', 'Use the optional microphone-based double-clap control where configured.', 'Microphone; enabled clap detection', '/docs/reference'],
    ['computer-settings', 'Computer Settings Assistance', 'Computer', 'Use supported system-settings actions while retaining owner permissions and confirmations.', 'Windows settings access', '/docs/reference'],
    ['remote-tunnel', 'Owner-Requested Port Tunnels', 'Remote Control', 'Manage supported port tunnels for explicitly requested remote access. Exposing a service requires owner approval.', 'Tunnel provider; owner authorization', '/docs/security'],
    ['tasks-proactive', 'Proactive Owner Notices', 'Tasks', 'Configure supported proactive notices and background checks for the owner, with delivery depending on the active session.', 'Desktop session; configured monitoring', '/docs/missions'],
    ['coding-search', 'Code Search & Helpers', 'Coding', 'Search project code and use configured code-generation helpers alongside supervised OpenCode work.', 'Project access; configured AI provider', '/docs/coding'],
    ['updates-game', 'Configured Game Update Assistance', 'Updates', 'Use the game-update tool for supported, configured update workflows.', 'Supported game configuration; internet connection', '/docs/reference'],
    ['distribution-windows-beta', 'Windows Beta Installer', 'Distribution', 'Install the published Windows beta using the official setup file and screenshot guide. The beta is unsigned.', 'Windows 10/11 64-bit', '/docs/install-windows'],
    ['updates-manual-beta', 'Official Release & Update Checks', 'Updates', 'Find official releases and check update availability. Unsigned desktop betas require manual installation; automatic installation accepts signed releases only.', 'Official release channel; internet connection', '/releases'],
  ] as const).map(([id, name, category, description, dependency, docsLink]): FeatureItem => ({
    id, name, category, shortDescription: description, detailedDescription: description,
    status: 'BETA', platform: id.startsWith('phone-') ? 'ANDROID' : 'WINDOWS',
    privacy: ['Browser', 'Tasks', 'Files', 'Phone Video', 'Plugins', 'Updates'].includes(category) ? 'OPTIONAL CLOUD' : 'LOCAL',
    dependencies: dependency.split('; '), docsLink,
  })),
];
