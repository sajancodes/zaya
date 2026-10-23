export interface DocItem {
  id: string;
  title: string;
  category: string;
  description: string;
  content: string;
}

export const DOCS_CATEGORIES = [
  'Getting Started',
  'Installation',
  'Voice & Audio',
  'AI Providers',
  'Operating System',
  'Sensory & Vision',
  'Spatial & Hands',
  'Continuity & Mobile',
  'Security & Architecture',
  'Reference'
] as const;

export const DOCS_DATA: Record<string, DocItem> = {
  'getting-started': {
    id: 'getting-started',
    title: 'Getting Started with Zaya',
    category: 'Getting Started',
    description: 'Complete walkthrough from initial download to your first conversational turn.',
    content: `
# Getting Started with Zaya

Zaya is a personal AI system created and developed by **Sajan Rai**. It operates directly on your Windows desktop, combining full-duplex conversational voice, screen perception, optical hand tracking, and 3D spatial intelligence into a single cohesive runtime.

> **System Requirements Checklist**:
> - Windows 10 (64-bit 1903+) or Windows 11
> - A working microphone and audio output
> - A Google AI Studio API key (free tier available) or a local LLM runner (Ollama)
> - Optional: Standard 720p/1080p webcam for optical hand tracking and spatial manipulation

---

## The 8-Step Setup Journey

1. **Check release availability**: Visit [/download](/download). The signed public Windows installer is not published yet; use only an artifact actually listed there after release verification.
2. **Run Installer**: Double-click \`ZayaSetup.exe\`. It installs binaries to \`%LOCALAPPDATA%\\Programs\\Zaya\` without requiring administrator elevation.
3. **Launch Zaya**: Launch from Start Menu or desktop shortcut. The animated companion appears on your taskbar.
4. **First-Run Wizard**: The onboarding window opens automatically to configure audio devices and provider credentials.
5. **Add Gemini API Key**:
   - Visit [Google AI Studio](https://aistudio.google.com/app/apikey).
   - Generate your free API key.
   - Paste the key into Zaya and click **Test Connection**. Zaya encrypts it with Windows DPAPI.
6. **Configure Voice Output**: Select the **Nika** voice tone or your preferred audio playback device.
7. **Optional Optical Tracking**: Enable hand tracking in Settings > Hand controls & 3D workspace. (The camera remains completely OFF at startup).
8. **Start Speaking**: Address Zaya naturally or use your configured push-to-talk hotkey.
`
  },

  'install-windows': {
    id: 'install/windows',
    title: 'Windows Installation Guide',
    category: 'Installation',
    description: 'Detailed setup instructions, directories, DPAPI encryption, and background updater.',
    content: `
# Windows Installation Guide

Zaya is optimized for Windows 10/11 64-bit desktop environments.

---

## Directory Architecture

When installed via \`ZayaSetup.exe\`, files reside in isolated user-space directories:

| Component | Path |
| --- | --- |
| Application Binaries | \`%LOCALAPPDATA%\\Programs\\Zaya\` |
| User Configuration | \`%LOCALAPPDATA%\\Zaya\\config\\api_keys.json\` (DPAPI encrypted) |
| Local Memory Archive | \`%LOCALAPPDATA%\\Zaya\\memory\\conversation.db\` |
| Runtime Diagnostics | \`%LOCALAPPDATA%\\Zaya\\logs\\runtime\\events.jsonl\` |

---

## Silent / Automated Command Line Install

For enterprise or scripted setup:

\`\`\`powershell
# Run silent installation
.\\ZayaSetup.exe /S /ALLUSERS=0

# Verify installation status
Test-Path "$env:LOCALAPPDATA\\Programs\\Zaya\\Zaya.exe"
\`\`\`
`
  },

  'install-android': {
    id: 'install/android',
    title: 'Android Companion Installation',
    category: 'Installation',
    description: 'Native Jetpack Compose companion installation, permissions, and encrypted pairing.',
    content: `
# Android Companion Installation

The Zaya Android companion is a native Kotlin application built with Jetpack Compose. It connects directly to your desktop instance over local Wi-Fi or LAN.

---

## Download & Installation

1. Download \`Zaya-Companion.apk\` from [/download](/download) or the official GitHub release.
2. Tap the APK on your phone and allow installation from unknown sources.
3. Open **Zaya Companion**.

---

## 6-Character Encrypted Pairing

1. On your Windows desktop, open **Settings & Controls → Remote Control**.
2. Note the generated **6-character pairing code**.
3. In the Android companion app, enter the desktop LAN IP and pairing code.
4. The key is securely saved in the **Android Hardware Keystore**.
`
  },

  'install-source': {
    id: 'install/source',
    title: 'Source Installation & Developer Setup',
    category: 'Installation',
    description: 'Cloning from GitHub, creating Python 3.13 venvs, and compiling dependencies.',
    content: `
# Installing from Source

If you are a developer or researcher wishing to inspect and run Zaya from source:

\`\`\`powershell
# 1. Clone repository
git clone https://github.com/sajancodes/zaya.git
cd zaya

# 2. Create Python 3.13 virtual environment
py -3.13 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1

# 3. Install core dependencies & Playwright
python setup.py
playwright install chromium firefox

# 4. Optional: Hand tracking isolated environment
powershell -ExecutionPolicy Bypass -File tools\\setup_hands.ps1

# 5. Launch Zaya
python main.py
\`\`\`
`
  },

  'voice': {
    id: 'voice',
    title: 'Voice Architecture & Gemini Live',
    category: 'Voice & Audio',
    description: 'Full-duplex WebSocket audio streaming, Nika voice synthesis, acoustic interruption, and ducking.',
    content: `
# Voice Architecture & Acoustic Intelligence

Zaya utilizes bidirectional full-duplex WebSocket audio streaming powered by **Google Gemini Live** (\`models/gemini-3.8-live\`).

---

## Core Audio Capabilities

### 1. Acoustic Barge-In (Interruption)
You can interrupt Zaya at any moment while she speaks. An on-device WebRTC VAD filter continuously samples your microphone. When your voice begins, the desktop speaker buffer is immediately truncated, ducked audio restores, and active listening resumes.

### 2. Windows CoreAudio Ducking
During spoken dialogue (either yours or Zaya's), background computer audio drops to 20% of its previous volume. When the turn concludes, background sound smoothly fades back to 100%.

\`\`\`json
"audio_ducking": {
  "enabled": true,
  "background_ratio": 0.2,
  "voice_volume": 1.0,
  "release_seconds": 0.8
}
\`\`\`

### 3. Nika Voice Persona
Zaya's voice synthesis is tuned to the **Nika** personality delivery model, expressing nuanced affective delivery based on conversation context.
`
  },

  'providers': {
    id: 'providers',
    title: 'AI Providers & Multi-Key Failover',
    category: 'AI Providers',
    description: 'Connecting Gemini, OpenAI, OpenRouter, Groq, DeepSeek, and setting up automatic rate-limit failover.',
    content: `
# AI Providers & Key Configuration

Zaya is model-agnostic. The intelligence layer can change while tools, memory, and desktop operators remain completely intact.

---

## Multi-Key Rate Limit (429) Failover

Configure multiple Gemini keys in a comma-separated list:

\`\`\`text
AIzaSyKeyOne..., AIzaSyKeyTwo..., AIzaSyKeyThree...
\`\`\`

When Gemini returns a \`429 Quota Exceeded\` error, Zaya automatically rotates to the next available key and reconnects without losing your ongoing conversation.
`
  },

  'local-ai': {
    id: 'local-ai',
    title: 'Modular Local AI Engine (100% Offline)',
    category: 'AI Providers',
    description: 'Running faster-whisper, Ollama/llama.cpp, and Piper ONNX completely offline.',
    content: `
# Modular Local AI Engine

For maximum privacy, Zaya includes a split modular pipeline that runs entirely on-device without any cloud internet calls:

\`\`\`text
Microphone → WebRTC VAD → faster-whisper → Local LLM (Ollama) → Piper ONNX → Speaker
\`\`\`

---

## Setup Steps

1. Install local speech dependencies:
\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pip install -r requirements-local-speech.txt
\`\`\`
2. Install [Ollama](https://ollama.com) and pull your model:
\`\`\`bash
ollama run qwen2.5:14b
\`\`\`
3. In Zaya Settings > AI ENGINE, select **LOCAL PIPELINE**, choose Ollama, and supply your Piper ONNX model path.
`
  },

  'computer-control': {
    id: 'computer-control',
    title: 'Operating System Control & UIA',
    category: 'Operating System',
    description: 'Hierarchical desktop execution: Native Win32, Browser DOM, Windows UIA, and coordinates.',
    content: `
# Operating System Control Architecture

Zaya follows a strict **Observe → Identify → Act → Verify** execution loop.

---

## Fallback Hierarchy

1. **Native Control**: Win32 process spawn, ShellExecute, window focus.
2. **Browser DOM**: Playwright element locator hierarchy.
3. **Windows UI Automation (UIA)**: Direct inspection of accessible controls, buttons, text fields.
4. **Set-of-Mark (SoM)**: Overlaying numerical tags onto Candidate UI elements.
5. **Vision Segmentation**: Multimodal vision model bounding box calculation.
6. **Coordinate Fallback**: Direct cursor click with post-action difference verification.
`
  },

  'browser': {
    id: 'browser',
    title: 'Browser Automation & Recovery',
    category: 'Operating System',
    description: 'Native browser launching alongside deep Playwright DOM automation and context recovery.',
    content: `
# Browser Automation & Context Recovery

Zaya operates browsers through two complementary pathways:

- **Native Launch**: Opens URLs in your standard default browser (Brave, Chrome, Firefox) retaining your normal profile and logins.
- **Automated Playwright**: Launches isolated Chromium or Firefox instances for deep interactive automation (form completion, automated testing, extraction).

If an automated browser window closes unexpectedly, Zaya invalidates the stale context and re-initializes on the next request.
`
  },

  'vision': {
    id: 'vision',
    title: 'Vision & Screen Understanding',
    category: 'Sensory & Vision',
    description: 'On-demand multimodal visual inspection of desktop screens, error dialogs, and diagrams.',
    content: `
# Vision & Screen Understanding

Zaya captures high-resolution desktop or window regions only when explicitly requested.

---

## How It Works

1. **Explicit Trigger**: You say *"Zaya, look at this error"* or *"What's wrong with this code?"*.
2. **Focused Window Capture**: Captures only the active foreground window, minimizing background clutter.
3. **Multimodal Analysis**: Passes image frames to your configured vision model (Gemini Vision, GPT-4o, or Pixtral).
4. **Structured Explanation**: Returns actionable diagnostic advice.
`
  },

  'perception': {
    id: 'perception',
    title: 'Continuous Local Screen Perception',
    category: 'Sensory & Vision',
    description: 'Zero-cloud differential frame hashing, active window tracking, and in-memory OCR.',
    content: `
# Continuous Local Screen Perception

Unlike cloud-dependent assistants that stream continuous video feeds of your screen, Zaya's perception engine is **100% on-device**:

- **Differential Frame Hashing**: Sub-5ms screen hashing using \`mss\` and OpenCV.
- **Active Window Tracker**: Monitors active processes and window titles locally.
- **In-Memory OCR**: Windows native WinRT OCR streaming via memory buffers without writing PNG files to disk.
- **Zero Cloud Video**: Not a single continuous frame is sent across the internet.
`
  },

  'hand-control': {
    id: 'hand-control',
    title: 'Optical Hand Tracking',
    category: 'Spatial & Hands',
    description: 'MediaPipe 21-joint skeleton tracking at 30 FPS in an isolated worker process.',
    content: `
# Optical Hand Tracking

Operate your computer in mid-air using a standard webcam.

---

## Architectural Isolation

Hand tracking runs inside an isolated sub-process (\`ZayaHandWorker.exe\`) in a dedicated virtual environment (\`.venv-hands\`). Zero LLMs run in the interaction loop, achieving **30 FPS** and ultra-low latency.

### Gesture Mappings
- **Open Palm**: Cursor position control
- **Index Poke**: Click with adaptive depth latching
- **Two Fingers**: Drag selection and highlighting
- **Closed Fist**: Continuous scrolling
- **Thumbs Up**: Enter / Confirm
`
  },

  'air-keyboard': {
    id: 'air-keyboard',
    title: 'Depth-Invariant Air Keyboard',
    category: 'Spatial & Hands',
    description: 'Mid-air typing with palm-relative depth adaptation, debouncing, and security guards.',
    content: `
# Depth-Invariant Air Keyboard

Projects a translucent virtual keyboard in mid-air.

---

## Safety & Security Guards

- **Palm-Relative Depth Adaptation**: Key strike thresholds adapt automatically as your hand moves closer or further from the webcam.
- **Hysteresis Debouncing**: Prevents phantom double-typing.
- **Anti-Self-Entry Guard**: Zaya's virtual keyboard strictly refuses to inject keystrokes into its own credential dialogs or elevated system prompts.
`
  },

  'spatial': {
    id: 'spatial',
    title: '3D Spatial Workspace',
    category: 'Spatial & Hands',
    description: 'Interactive Babylon.js WebGPU canvas, GLB/glTF streaming, and natural language scene planner.',
    content: `
# 3D Spatial Intelligence Workspace

Zaya features a dedicated 3D canvas built with **Babylon.js** supporting WebGPU with WebGL fallback.

---

## Spatial Capabilities

- **Progressive GLB/glTF Streaming**: Progressively stream and render mechanical assemblies.
- **Exploded Views**: Smooth animated component expansion along assembly axes.
- **X-Ray Inspection**: Transparent casing shaders for internal mechanical inspection.
- **Natural Language Spatial Planner**: Issue commands like *"Make the casing transparent and explode the piston assembly"*.
`
  },

  'memory': {
    id: 'memory',
    title: 'Memory & SQLite FTS5 Archive',
    category: 'Security & Architecture',
    description: 'Persistent conversation archive with BM25 full-text indexing and max-5 message on-demand recall.',
    content: `
# Memory & Knowledge Store Architecture

Zaya saves all dialogues locally in \`memory/conversation.db\`.

---

## Principles of Memory Design

1. **Zero Preload on Startup**: A fresh Zaya session starts clean with 0 Gemini input tokens spent on old history.
2. **On-Demand Recall**: When asked *"What were we discussing yesterday?"*, Zaya queries the local SQLite FTS5 store for **at most five relevant messages**.
3. **Structured Knowledge Store**: Stores typed entities (PERSON, PROJECT, PREFERENCE, RELATIONSHIP, FACT).
`
  },

  'missions': {
    id: 'missions',
    title: 'Mission Supervisor & Autonomy',
    category: 'Security & Architecture',
    description: '10-state lifecycle state machine with bounded retries, task evidence, and crash recovery.',
    content: `
# Mission Supervisor & Autonomy

Long-running autonomous workflows are managed by the **Mission Supervisor**.

---

## 10-State Lifecycle Machine

- \`PLANNING\`: Structured goal decomposition
- \`RUNNING\`: Worker task execution
- \`WAITING CONFIRMATION\`: Destructive step paused for owner approval
- \`WAITING CLARIFICATION\`: Ambiguous instruction requires input
- \`WAITING EXTERNAL\`: Paused for compilation, download, or external webhook
- \`PAUSED\`: Owner-paused execution
- \`INTERRUPTED\`: Owner speech turn took priority
- \`COMPLETED\`: Verified proof-of-work recorded
- \`UNVERIFIED\`: Action finished but unable to inspect DOM
- \`FAILED\`: Bounded retry limit reached; logs saved
`
  },

  'coding': {
    id: 'coding',
    title: 'Supervised OpenCode Orchestrator',
    category: 'Operating System',
    description: 'Multi-pass coding assistant managing OpenCode CLI with automated testing and review.',
    content: `
# Supervised OpenCode Orchestration

Zaya coordinates complex software engineering tasks through the installed OpenCode CLI.

---

## Supervised Pipeline

1. **Owner Request**: Spoken natural task (e.g. *"Build a calculator"*).
2. **Zaya Brief**: Compiles concrete behavior, edge cases, and run instructions.
3. **OpenCode Session**: Prompts the CLI in a hidden background worker.
4. **Git Diff Tracking**: Tracks modified, added, and deleted files.
5. **Test Runner**: Executes unit tests and smoke tests.
6. **Tool-Free Review**: Checks observed output against the original brief.
7. **Strict 3-Pass Ceiling**: Caps automated corrections at 3 passes to prevent prompt looping.
`
  },

  'whatsapp': {
    id: 'whatsapp',
    title: 'WhatsApp Hermes Gateway Link',
    category: 'Continuity & Mobile',
    description: 'Persistent linked-device session, Observe/Draft/Auto modes, and strict privacy boundaries.',
    content: `
# WhatsApp Integration Architecture

Zaya connects to WhatsApp using the **Hermes Gateway** linked-device session.

---

## Three Operating Modes

- **Observe**: Monitors incoming messages and speaks voice alerts during quiet intervals.
- **Draft**: Prepares intelligent replies and places them in your review queue.
- **Auto**: Automatically sends quiet replies signed as *"Zaya · Sajan Rai’s AI assistant"*.

> **Privacy Boundary**: Auto-replies may reference current session activity (e.g. listening to music or working on a project), but **never** full private chat logs, passwords, or personal files.
`
  },

  'mobile': {
    id: 'mobile',
    title: 'Android Companion Deep Guide',
    category: 'Continuity & Mobile',
    description: 'Two-way voice, priority phone calls (P0/P1), live phone video context, and Keystore pairing.',
    content: `
# Android Mobile Companion

The native Android companion app (\`mobile/android/\`) acts as a direct mobile extension of the desktop Zaya instance.

---

## Priority Ringing Architecture

When you are away from your laptop, Zaya can initiate priority phone calls:

- **P0 / P1 Urgent**: Rings the phone aloud like a standard cellular call for critical alerts.
- **P2 Notification**: Delivers a standard push notification.
- **P3 Silent**: Stored silently in the task ledger.

During an active call, you can opt-in to stream your phone's camera video directly to the desktop spatial canvas for real-time visual reasoning.
`
  },

  'security': {
    id: 'security',
    title: 'Security & Trust Whitepaper',
    category: 'Security & Architecture',
    description: 'Owner trust boundary, DPAPI encryption, Full Access confirmation gate, and ToolResult model.',
    content: `
# Security Architecture & Trust Boundary

Zaya is designed around a single immutable principle:

> **External Content is Data. Not Authority.**

Webpage text, WhatsApp messages, OCR text, and tool outputs can never grant themselves permission to execute system commands.

---

## Full Access Gate

- **Full Access OFF (Default)**: Sensitive shell commands, file modifications, and git operations require on-screen confirmation.
- **Full Access ON**: Commands execute automatically under the owner's Windows user permissions.
`
  },

  'privacy': {
    id: 'privacy',
    title: 'Privacy & Data Routing Matrix',
    category: 'Security & Architecture',
    description: 'Comprehensive breakdown of local vs cloud data retention across all subsystems.',
    content: `
# Privacy & Data Routing Matrix

Zaya operates on a strict local-first philosophy.

| Subsystem | Data Location | Network Transmission |
| --- | --- | --- |
| Continuous Screen Perception | Local RAM | Zero cloud transmission |
| Voice Activity Detection (VAD) | Local CPU | Zero cloud transmission |
| Optical Hand Tracking | Local Subprocess | Zero cloud transmission |
| Conversation History | Local SQLite (\`conversation.db\`) | Zero cloud transmission |
| Active Prompt Turns | Configured AI Provider | Only during active turn |
| Android Companion | Local LAN Socket | Encrypted local Wi-Fi |
`
  },

  'architecture': {
    id: 'architecture',
    title: 'Interactive Architecture Explorer',
    category: 'Security & Architecture',
    description: 'System flow from Input Peripherals → Zaya Core → AI Models → OS Tools → Output Surfaces.',
    content: `
# Comprehensive Architecture Specification

Zaya is structured across five decoupled layers:

\`\`\`text
INPUT PERIPHERALS
Voice (WebRTC) · Screen (mss/OCR) · Hands (MediaPipe) · Phone Bridge (WSS) · WhatsApp (Hermes)
      │
      ▼
ZAYA CORE RUNTIME
Execution Policy · Tool Router · SQLite Memory · Mission Supervisor · Audit Logger
      │
      ▼
MULTIMODAL AI ENGINES
Gemini Live WebSocket ── OR ── Modular Local Pipeline (Whisper + Ollama + Piper)
      │
      ▼
OPERATING SYSTEM ACTUATORS
Win32 Operator · UIA Automation · Playwright Browser · OpenCode CLI · Git Controller
      │
      ▼
OUTPUT SURFACES
Nika Speech Audio · Taskbar Companion · Spatial 3D Canvas · Android Calls & Video
\`\`\`
`
  },

  'configuration': {
    id: 'configuration',
    title: 'Configuration Reference',
    category: 'Reference',
    description: 'Complete breakdown of zayabar.json, api_keys.json, and environment settings.',
    content: `
# Configuration Reference

## \`zayabar.json\` (Root Companion Config)

\`\`\`json
{
  "assets": {
    "standby": "assets/standby.gif",
    "thinking": "assets/thinking.png",
    "poked": "assets/poked.png",
    "talking": {
      "neutral": "assets/neutral.png",
      "happy": "assets/happy.png",
      "sad": "assets/sad.png",
      "angry": "assets/angry.png",
      "surprised": "assets/surprised.png"
    }
  },
  "audio_ducking": {
    "enabled": true,
    "background_ratio": 0.2,
    "voice_volume": 1.0,
    "release_seconds": 0.8
  }
}
\`\`\`
`
  },

  'troubleshooting': {
    id: 'troubleshooting',
    title: 'Troubleshooting & Diagnostics',
    category: 'Reference',
    description: 'Resolving microphone issues, rate-limits, Playwright browser locks, and crash recovery.',
    content: `
# Troubleshooting & Diagnostics

## Common Issues & Resolutions

### 1. Gemini Live Rate Limit (429)
- **Symptom**: Zaya shows *"Quota cooling down"*.
- **Fix**: Right-click Zaya > **Gemini API keys...** and add multiple comma-separated keys for automatic rotation.

### 2. Microphone Not Detected
- **Symptom**: Speech turns do not trigger.
- **Fix**: Open **Settings & Controls > Audio Devices** and verify that your default recording device is selected.

### 3. Hand Tracking Performance
- **Symptom**: Jittery hand landmarks.
- **Fix**: Ensure adequate room lighting and run \`powershell tools\\setup_hands.ps1\` to verify MediaPipe weights.
`
  },

  'reference': {
    id: 'reference',
    title: 'Complete Tool & API Reference',
    category: 'Reference',
    description: 'Full programmatic dictionary of all action tools, parameters, and return signatures.',
    content: `
# Complete Tool & Action Reference

Zaya includes dozens of built-in action tools callable by the AI reasoning engine:

- \`open_app(app_name)\`: Launch desktop application by name or path.
- \`computer_control(action, target, coords)\`: Win32/UIA desktop operator.
- \`browser_control(url, mode, action)\`: Playwright web automation.
- \`coding_job(action, project, task)\`: Supervised OpenCode coding sessions.
- \`spatial_workspace(action, command)\`: 3D WebGPU canvas operations.
- \`whatsapp_control(action, contact, message)\`: WhatsApp message handling.
- \`mobile_call(action, priority, reason)\`: Place priority phone call to Android companion.
`
  }
};
