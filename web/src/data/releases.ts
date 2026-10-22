export interface ReleaseItem {
  version: string;
  tag: string;
  channel: 'Stable' | 'Beta' | 'Preview';
  platform: 'windows' | 'android' | 'cross-platform';
  platformName: string;
  date: string;
  filename: string;
  downloadUrl: string;
  sha256: string;
  sizeBytes: number;
  sizeFormatted: string;
  highlights: string[];
  fullChangelog: string[];
  knownIssues?: string[];
  requirements: string[];
}

export const RELEASES_DATA: ReleaseItem[] = [
  {
    version: '0.5.0',
    tag: 'v0.5.0',
    channel: 'Stable',
    platform: 'windows',
    platformName: 'Windows Desktop',
    date: 'October 22, 2026',
    filename: 'ZayaSetup.exe',
    downloadUrl: 'https://github.com/sajancodes/zaya-companion-releases/releases/download/v0.5.0/ZayaSetup.exe',
    sha256: 'fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1',
    sizeBytes: 48500000,
    sizeFormatted: '46.2 MB',
    highlights: [
      'Vision Control Center: continuous local perception without screenshot spam',
      'Optical Hand Tracking: MediaPipe 21-point tracking running in isolated worker',
      'Depth-Invariant Virtual Keyboard: mid-air typing with hysteresis debouncing',
      'Babylon.js 3D Spatial Canvas: interactive progressive scene streaming',
      'Windows DPAPI Hardware-Backed Encryption for user secrets'
    ],
    fullChangelog: [
      'Added MediaPipe Hand Landmarker child process running at 30 FPS with zero UI contention.',
      'Implemented Ghost Keyboard with palm-relative depth adaptation and anti-self-entry security guard.',
      'Introduced Babylon.js WebGPU / WebGL 3D spatial intelligence workspace with GLB/glTF import.',
      'Added differential screen frame hashing and Windows native in-memory OCR stream.',
      'Secured all API keys and pairings with Windows DPAPI encryption (api_keys.json).',
      'Enhanced mission supervisor with 10-state lifecycle and durable SQLite rollback checkpointing.'
    ],
    knownIssues: [
      'Optical hand tracking requires consistent ambient lighting and a standard webcam (720p+ recommended).',
      'First-run faster-whisper model download requires 150MB-500MB temporary network bandwidth.'
    ],
    requirements: [
      'Windows 10 (64-bit) 1903+ or Windows 11',
      '4GB RAM minimum (8GB recommended for spatial rendering)',
      'Working microphone and audio output',
      'Optional: Standard 720p/1080p webcam for hand tracking'
    ]
  },
  {
    version: '0.4.6',
    tag: 'android-0.4.6',
    channel: 'Stable',
    platform: 'android',
    platformName: 'Android Companion',
    date: 'October 21, 2026',
    filename: 'Zaya-Companion.apk',
    downloadUrl: 'https://github.com/sajancodes/zaya-companion-releases/releases/download/android-0.4.6/Zaya-Companion.apk',
    sha256: 'e89c6295efb867c2105e4d293d07e6e5a6a6fa34d580ce6ffcf06d4493ecfa25',
    sizeBytes: 24200000,
    sizeFormatted: '23.1 MB',
    highlights: [
      'Play Store install-source detection & dual-mode release compatibility',
      'Foreground service audio streaming stability during sleep',
      'Incoming Zaya call caller-ID notification and action buttons',
      'Opt-in camera video frame sharing over encrypted local socket'
    ],
    fullChangelog: [
      'Native Kotlin & Jetpack Compose UI rewrite with zero Flutter dependencies.',
      'Implemented Android Telecom framework hooks for real incoming call ringing (P0/P1).',
      'Encrypted pairing token storage using Android Hardware Keystore.',
      'Optimized H.264 camera video streaming to desktop spatial canvas.'
    ],
    knownIssues: [
      'Battery optimization must be set to "Unrestricted" for background call reliability on MIUI/OneUI.'
    ],
    requirements: [
      'Android 10 (API level 29) or higher',
      'Wi-Fi or LAN connection on same network as Zaya desktop',
      'Microphone and Camera permissions for voice and visual sharing'
    ]
  },
  {
    version: '0.4.2',
    tag: 'v0.4.2',
    channel: 'Stable',
    platform: 'windows',
    platformName: 'Windows Desktop',
    date: 'October 15, 2026',
    filename: 'ZayaSetup-0.4.2.exe',
    downloadUrl: 'https://github.com/sajancodes/zaya-companion-releases/releases/download/v0.4.2/ZayaSetup.exe',
    sha256: '4a1b89ef726a1b24cd582e01f5aa7c9e0d1b46ef023d8c47b59e358cf112a9bf',
    sizeBytes: 44100000,
    sizeFormatted: '42.0 MB',
    highlights: [
      'WhatsApp Hermes gateway link with per-chat Observe/Draft/Auto modes',
      'SQLite FTS5 knowledge store with max-5 message on-demand semantic recall',
      'CoreAudio Windows background audio ducking during voice turns',
      'Playwright browser recovery and context re-launch'
    ],
    fullChangelog: [
      'Added persistent Hermes WhatsApp session pairing with QR scanning.',
      'Restricted auto-reply context to current session activity with zero profile leakage.',
      'Integrated Playwright Chromium/Firefox automation with login page detection.',
      'Implemented audio ducking filter lowering background sounds to 20% during speech.'
    ],
    requirements: [
      'Windows 10/11 64-bit',
      'Google Gemini API key'
    ]
  }
];
