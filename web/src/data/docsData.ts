export interface DocItem {
  id: string;
  title: string;
  category: string;
  description: string;
  content: string;
}

export const DOCS_DATA: Record<string, DocItem> = {
  'getting-started': {
    id: 'getting-started',
    title: 'Getting Started with Zaya',
    category: 'Getting Started',
    description: 'Walkthrough from initial download to your first conversational command.',
    content: `
# Getting Started with Zaya

Zaya is an autonomous personal AI assistant created and developed by Sajan Rai. It runs directly on your Windows desktop, combining conversational voice, screen perception, optical hand tracking, and 3D spatial intelligence.

> **Quick Checklist**: You will need a Windows 10/11 64-bit computer, a working microphone, and a free Google AI Studio API key. A webcam is optional (only required for hand tracking and the virtual keyboard).

---

## The 8-Step Setup Journey

1. **Download ZayaSetup.exe**: Navigate to the [Download Page](/download) and download the official Windows installer.
2. **Run the Installer**: Double-click \`ZayaSetup.exe\`. The installer sets up Zaya in \`%LOCALAPPDATA%\\Programs\\Zaya\` without needing administrator privileges.
3. **Launch Zaya**: Check "Launch Zaya" on the installer finish screen or find Zaya in your Start Menu.
4. **Complete Onboarding**: The first-run onboarding wizard welcomes you and explains provider options.
5. **Connect Google Gemini**:
   - Click the **Open Google AI Studio** button inside onboarding.
   - Sign in with your Google account.
   - Click **Create API key** and copy it.
   - Return to Zaya, paste the key, and click **Test Connection**.
6. **Configure Audio**: Choose your preferred Live voice (*Nika*, *Puck*, *Charon*, *Kore*, *Fenrir*, or *Aoede*).
7. **Optional Optical Controls**: If you have a webcam, enable hand tracking and the virtual keyboard. (The camera remains completely **OFF** at normal startup).
8. **Start Using Zaya**: Say *"Hey Jarvis"* or press your push-to-talk key and start speaking naturally!
`
  },

  'api-key': {
    id: 'api-key',
    title: 'Obtaining and Configuring Your API Key',
    category: 'Getting Started',
    description: 'How to get a Google AI Studio API key and store it securely with Windows DPAPI.',
    content: `
# Obtaining Your AI API Key

Zaya connects to multimodal AI models using your own credentials. Your keys stay on your computer and are never sent to Zaya analytics servers or public repositories.

---

## Step-by-Step: Getting a Gemini API Key

1. Open [Google AI Studio API Keys](https://aistudio.google.com/app/apikey).
2. Sign in with your standard Google account.
3. Click **Create API key**.
4. Select a project or create a new project.
5. Copy the generated key (starts with \`AIzaSy...\`).
6. In Zaya, open Settings or the First-Run Wizard, paste your key, and click **Test Connection**.

---

## Security & Storage Architecture

Zaya protects your credentials with **Windows DPAPI (Data Protection API)**:

- **Account-Bound**: Keys are encrypted using your Windows user account credentials. Another Windows user or computer cannot read them.
- **Disk Protection**: Plaintext keys are never stored on disk in \`api_keys.json\`; they are stored with a \`dpapi:...\` encrypted envelope.
- **UI Masking**: Keys are masked in the UI (\`••••••••••••1234\`) and never printed to console logs.

---

## Usage Limits & Free Tier

Google AI Studio provides a free tier for personal development. Zaya is independent software and is not affiliated with Google.
`
  },

  'windows-installation': {
    id: 'windows-installation',
    title: 'Windows Installation Guide',
    category: 'Getting Started',
    description: 'System requirements, installation directories, startup configuration, and troubleshooting.',
    content: `
# Windows Installation Guide

Zaya is distributed as a self-contained Windows application installer (\`ZayaSetup.exe\`) designed for Windows 10 and 11 (64-bit).

---

## System Requirements

- **Operating System**: Windows 10 (Build 19041+) or Windows 11 (64-bit).
- **Processor**: x86-64 CPU (Intel Core i5 / AMD Ryzen 5 or newer recommended).
- **RAM**: 8 GB minimum (16 GB recommended for 3D spatial rendering and local vision perception).
- **Storage**: 500 MB free disk space.
- **Microphone**: Working microphone for voice interaction.
- **Webcam**: Optional 720p/1080p webcam for hand gesture tracking.

---

## Directory Architecture

Zaya strictly separates read-only binaries from mutable user data:

\`\`\`text
Application Binaries (Read-Only):
%LOCALAPPDATA%\\Programs\\Zaya\\
├── Zaya.exe                    (Main application executable)
├── ZayaHandWorker.exe          (Isolated MediaPipe/OpenCV worker)
├── spatial_renderer\\dist\\     (Three.js frontend)
└── unins000.exe                (Standard uninstaller)

Mutable User Data:
%LOCALAPPDATA%\\Zaya\\
├── config\\                     (api_keys.json, hand_controls.json)
├── memory\\                     (Local SQLite conversation & session store)
├── cache\\                      (Perception cache)
├── models\\                     (hand_landmarker.task weights)
├── updates\\                    (Staged update installers)
└── installation.json           (Anonymous installation UUID)
\`\`\`

---

## Automatic Windows Startup

During installation or onboarding, you can choose whether to start Zaya on sign-in. This uses the standard per-user registry location (\`HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\`). You can toggle this on or off anytime in Settings.
`
  },

  'android-installation': {
    id: 'android-installation',
    title: 'Android Companion Installation',
    category: 'Getting Started',
    description: 'Installing Zaya Companion APK, permissions overview, and local pairing.',
    content: `
# Android Companion Installation

The **Zaya Companion** application connects your smartphone to your laptop runtime for mobile conversational voice, cellular call answering, and notification sync.

---

## Installation Options

- **Google Play Store**: Track currently in pre-launch testing.
- **Direct Official APK**: Download the signed APK directly from the [Download Page](/download).

---

## Sideloading the APK

1. Download \`Zaya-Companion.apk\` on your phone.
2. Tap the downloaded file. When prompted, permit "Install unknown apps" for your browser.
3. Review permissions and tap **Install**.
4. Open the companion app and enter your laptop's local IP address or scan the pairing QR code.

---

## Permissions Overview

- **Microphone**: Voice commands to Zaya.
- **Phone State & Calls**: Identifies incoming callers and manages cellular calls.
- **Foreground Service**: Keeps the audio stream active when your screen is locked.
- **Notifications**: Mirrors reminders and status alerts.
`
  },

  'voice': {
    id: 'voice',
    title: 'Voice Interaction & Audio Control',
    category: 'Core Systems',
    description: 'Configuring microphones, speakers, push-to-talk, and Live voices.',
    content: `
# Voice Interaction & Audio Control

Zaya connects directly to Gemini Live bidirectional audio streaming for conversational responsiveness.

---

## Activation Modes

- **Continuous Conversation**: Speak naturally and interrupt anytime.
- **Push-to-Talk**: Hold your configured hotkey to talk; the mic shuts off when released.
- **Wake Word**: Assistant sleeps until it hears *"Hey Jarvis"* or *"Zaya"*.

---

## Available Voices

Zaya supports six prebuilt Gemini voices: **Nika** (default), **Puck**, **Charon**, **Kore**, **Fenrir**, and **Aoede**.
`
  },

  'vision': {
    id: 'vision',
    title: 'Vision Control Center & Screen Perception',
    category: 'Core Systems',
    description: 'Screen diff tracking, native Windows OCR, and camera privacy principles.',
    content: `
# Vision Control Center & Screen Perception

The Vision Control Center manages optical inputs and screen awareness while enforcing strict user privacy.

---

## Screen Perception Principles

- **Zero Screenshot Clutter**: Zaya streams bitmap regions directly to Windows native OCR via memory pipes. Temporary screenshot files are never written to disk.
- **Differential Frame Tracking**: Perception only activates when screen content changes, keeping CPU usage below 1%.
- **Camera Isolation**: Webcams are never accessed in the background. The camera is OFF at normal startup and activates only when hand controls or vision tools are explicitly opened.
`
  },

  'virtual-keyboard': {
    id: 'virtual-keyboard',
    title: 'Virtual Gesture Keyboard Guide',
    category: 'Core Systems',
    description: 'Operating the optical hand-tracking virtual keyboard with mid-air gesture typing.',
    content: `
# Virtual Gesture Keyboard Guide

Zaya features a mid-air virtual keyboard powered by isolated MediaPipe hand landmark tracking. You can type in any Windows text field without touching physical peripherals.

---

## How It Works

1. **Open Vision Control Center**: Click the camera icon on the Zaya HUD or speak *"Open hand keyboard"*.
2. **Hold Up Your Hand**: Position your hand 30 to 70 cm in front of the webcam.
3. **Target Keys**: Extend your index finger. A targeting cursor tracks your fingertip over the on-screen keyboard overlay.
4. **Poke to Type**: Push your finger forward toward the camera. Crossing the depth threshold triggers the key.
5. **Retract & Next Key**: Pull your finger back past the release threshold to arm the next keystroke.

---

## Safeguards

> **Anti-Self-Typing Guard**: Zaya detects when its own window or credential dialogs are active and suppresses virtual keyboard key injection to prevent self-entry loops.
`
  },

  'spatial-workspace': {
    id: 'spatial-workspace',
    title: 'Spatial 3D Workspace Guide',
    category: 'Core Systems',
    description: 'Generating, inspecting, and manipulating interactive 3D mechanical schematics.',
    content: `
# Spatial 3D Workspace Guide

The Spatial Workspace generates interactive 3D engineering schematics that you can inspect, rotate, explode, and slice in real time.

---

## Opening the Workspace

Say *"Open spatial workspace"* or click the 3D cube icon on the Zaya HUD. An interactive Three.js window opens alongside your workspace.

---

## Core Spatial Commands

- **Generation**: Say *"Generate an inline 4-cylinder engine"*, *"Show a jet turbine"*, or *"Create a robotic arm"*.
- **Component Explosion**: Say *"Explode components"*. Zaya calculates functional radial displacement vectors and smoothly separates every part along its mechanical axis.
- **Cross-Section Slicing**: Say *"Slice on the X plane"* to expose internal pistons, bearings, and fluid channels.
- **Inspection & Undo**: Point to any component to highlight its metadata. Say *"Undo"* to revert the last manipulation.
`
  },

  'phone-pairing': {
    id: 'phone-pairing',
    title: 'Phone Pairing & Remote Call Handling',
    category: 'Core Systems',
    description: 'Connecting the Android Companion to desktop Zaya.',
    content: `
# Phone Pairing & Cellular Integration

Pairs your Android smartphone to Zaya desktop over your home Wi-Fi or secure encrypted tunnel.

---

## How to Pair

1. Connect both your phone and laptop to the same local network.
2. Open Zaya on your desktop and navigate to **Phone Companion Settings**.
3. Open **Zaya Companion** on your phone and tap **Pair New Desktop**.
4. Scan the QR code or enter the local IP address displayed on your desktop.
`
  },

  'whatsapp': {
    id: 'whatsapp',
    title: 'Safe WhatsApp Integration',
    category: 'Core Systems',
    description: 'Voice message alerts, activity status, and owner-only authorization gate.',
    content: `
# Safe WhatsApp Integration

Zaya connects to WhatsApp with strict privacy safeguards:

- **Activity-Only Context**: Auto-replies use only your current owner activity (e.g. current song or active project); full private chat history is never exposed to LLMs.
- **Owner Voice Alerts**: Urgent messages and explicit pass-along requests are spoken aloud to the owner.
- **No Remote Code Execution**: External WhatsApp messages cannot trigger desktop commands.
`
  },

  'automation': {
    id: 'automation',
    title: 'Scheduled Automations & Background Tasks',
    category: 'Core Systems',
    description: 'Creating recurring reminders, system tasks, and background automations.',
    content: `
# Scheduled Automations & Background Tasks

Zaya includes a persistent scheduler for background automations and morning briefings.

---

## Examples

- *"Remind me every weekday at 9 AM to check deployment logs."*
- *"Run morning briefing every morning at 8:00 AM."*
- *"Check for desktop updates daily."*
`
  },

  'troubleshooting': {
    id: 'troubleshooting',
    title: 'Troubleshooting & Problem Resolution',
    category: 'Maintenance & Security',
    description: 'Solutions for API key errors, audio issues, SmartScreen warnings, and camera freeze.',
    content: `
# Troubleshooting Guide

Solutions for common questions and setup issues:

---

## 1. "Invalid API Key" or Connection Rejected
Verify that you copied the complete key starting with \`AIzaSy...\` from [Google AI Studio](https://aistudio.google.com/app/apikey). Check that your Google Cloud project has Generative Language API enabled.

---

## 2. Windows SmartScreen Warning
When running a newly published \`ZayaSetup.exe\`, Windows Defender SmartScreen may display *"Windows protected your PC"* because community download volume is newly building. Click **More info** and then **Run anyway**.

---

## 3. Microphone Not Picking Up Voice
Check Windows Settings > Privacy & Security > Microphone, and confirm that desktop apps are allowed to access your microphone. Press **F4** to verify that Zaya is not muted.

---

## 4. Webcam / Hand Tracking Stuck on STARTING
Confirm that another application (Zoom, Teams, Discord) is not locking the webcam exclusively. Close other camera apps and restart Vision Control Center.
`
  },

  'uninstall': {
    id: 'uninstall',
    title: 'Uninstalling Zaya',
    category: 'Maintenance & Security',
    description: 'Complete removal instructions and user data management.',
    content: `
# Uninstalling Zaya

Zaya provides a clean uninstaller that removes application binaries while offering you the choice to preserve or erase your local memory and configurations.

---

## How to Uninstall

1. Open Windows **Settings > Apps > Installed Apps**.
2. Locate **Zaya** in the list.
3. Click the three dots and select **Uninstall**.
4. The uninstaller will ask: *"Would you like to remove your local Zaya data (memory, logs, cached models) as well?"*
   - Select **No** if you wish to keep your configurations and local databases for future installations.
   - Select **Yes** to completely delete \`%LOCALAPPDATA%\\Zaya\` and leave zero traces on your system.
`
  }
};
