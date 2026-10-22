"""Comprehensive documentation articles for Zaya.
Created and developed by Sajan Rai.

Every guide provides exact operational steps, commands, and security disclosures.
"""
from __future__ import annotations

from typing import Dict

DOCS_ARTICLES: Dict[str, Dict[str, str]] = {
    "getting-started": {
        "title": "Getting Started with Zaya",
        "description": "Step-by-step walkthrough from initial download to your first conversational command.",
        "html": """
<h1>Getting Started with Zaya</h1>
<p>Zaya is an autonomous personal AI assistant created and developed by Sajan Rai. It runs directly on your Windows desktop, combining conversational voice, screen perception, optical hand tracking, and 3D spatial intelligence.</p>

<div class="callout">
  <b>Quick Checklist:</b> You will need a Windows 10/11 64-bit computer, a working microphone, and a free Google AI Studio API key. A webcam is optional (only required for hand tracking and virtual keyboard).
</div>

<h2>The 8-Step Setup Journey</h2>
<ol>
  <li><b>Download ZayaSetup.exe</b>: Visit <a href="/download">zaya.sajan.codes/download</a> and download the official installer.</li>
  <li><b>Run the Installer</b>: Double-click <code>ZayaSetup.exe</code>. The installer places application binaries into <code>%LOCALAPPDATA%\\Programs\\Zaya</code> without requiring administrator privileges.</li>
  <li><b>Launch Zaya</b>: At the end of installation, check "Launch Zaya" or open Zaya from your Start Menu.</li>
  <li><b>Complete Onboarding</b>: The first-run wizard welcomes you and guides you through provider selection and permissions.</li>
  <li><b>Connect Google Gemini</b>:
    <ul>
      <li>Click the <b>Open Google AI Studio</b> button in onboarding.</li>
      <li>Sign in and generate your free API key.</li>
      <li>Paste the key into Zaya and click <b>Test Connection</b>.</li>
    </ul>
  </li>
  <li><b>Configure Audio</b>: Allow microphone access and select your preferred Live voice (Nika, Puck, Charon, Kore, Fenrir, or Aoede).</li>
  <li><b>Optional Optical Controls</b>: If you have a webcam, you can enable the Vision Control Center and hand gesture tracking from settings. (Camera remains completely OFF at normal startup).</li>
  <li><b>Start Interacting</b>: Say "Hey Jarvis" or hold your push-to-talk key and ask Zaya a question, request desktop assistance, or generate a 3D schematic!</li>
</ol>
"""
    },

    "api-key": {
        "title": "Obtaining and Configuring Your AI API Key",
        "description": "How to get a free Google AI Studio Gemini API key and store it securely in Zaya.",
        "html": """
<h1>Obtaining Your AI API Key</h1>
<p>Zaya connects to high-performance multimodal models using your own API credentials. Your keys are stored locally on your computer and are never transmitted to Zaya analytics servers or public repositories.</p>

<h2>Step-by-Step: Getting a Gemini API Key</h2>
<ol>
  <li>Navigate to <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener">Google AI Studio API Keys</a>.</li>
  <li>Sign in with your standard Google account.</li>
  <li>Click <b>Create API key</b>.</li>
  <li>Select an existing Google Cloud project or create a new one (takes 5 seconds).</li>
  <li>Copy the newly generated key string (it starts with <code>AIzaSy...</code>).</li>
  <li>Open Zaya, navigate to Settings or the Onboarding Wizard, paste the key, and click <b>Test Connection</b>.</li>
</ol>

<div style="margin: 20px 0;">
  <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener" class="btn btn-primary">
    Open Google AI Studio ↗
  </a>
</div>

<h2>Security & Storage Architecture</h2>
<p>Zaya protects your credentials with <b>Windows DPAPI (Data Protection API)</b>:</p>
<ul>
  <li><b>Account-Bound</b>: The encrypted key can only be decrypted by the logged-in Windows user account on that specific machine.</li>
  <li><b>Disk Protection</b>: Plaintext keys are never written to disk in <code>api_keys.json</code>; they are saved with a <code>dpapi:...</code> envelope.</li>
  <li><b>UI Masking</b>: Keys are automatically masked in the user interface (e.g. <code>••••••••••••1234</code>) and are never output to logs or terminal streams.</li>
</ul>

<h2>Usage Limits & Costs</h2>
<p>Google AI Studio offers a generous free tier for personal projects. Please note that Zaya is independent software and is not affiliated with Google. Usage is governed by your agreement with Google AI Studio.</p>
"""
    },

    "windows-installation": {
        "title": "Windows Installation Guide",
        "description": "System requirements, installation directories, startup configuration, and troubleshooting.",
        "html": """
<h1>Windows Installation Guide</h1>
<p>Zaya is distributed as a self-contained Windows application installer (<code>ZayaSetup.exe</code>) designed for Windows 10 and Windows 11 (64-bit).</p>

<h2>System Requirements</h2>
<ul>
  <li><b>Operating System</b>: Windows 10 (Version 2004 or later) / Windows 11 (64-bit).</li>
  <li><b>Processor</b>: x86-64 compatible CPU (Intel Core i5 / AMD Ryzen 5 or newer recommended).</li>
  <li><b>RAM</b>: 8 GB minimum (16 GB recommended for 3D spatial rendering and local vision perception).</li>
  <li><b>Storage</b>: 500 MB free space for application binaries and cache.</li>
  <li><b>Hardware</b>: Working microphone for voice interaction; optional 720p/1080p webcam for hand gesture tracking.</li>
</ul>

<h2>Directory Architecture</h2>
<p>Zaya strictly isolates mutable user data from read-only application binaries:</p>
<div class="code-block">
Application Binaries (Read-Only):
%LOCALAPPDATA%\\Programs\\Zaya\\
├── Zaya.exe                    (Main PyQt6 application executable)
├── ZayaHandWorker.exe          (Isolated MediaPipe/OpenCV worker)
├── spatial_renderer\\dist\\     (Three.js web frontend)
└── unins000.exe                (Standard uninstaller)

Mutable User Data:
%LOCALAPPDATA%\\Zaya\\
├── config\\                     (api_keys.json, hand_controls.json)
├── memory\\                     (Local SQLite conversation & session store)
├── cache\\                      (Temporary OCR & perception assets)
├── models\\                     (hand_landmarker.task weights)
├── updates\\                    (Staged update installer binaries)
└── installation.json           (Anonymous installation UUID)
</div>

<h2>Automatic Windows Startup</h2>
<p>During installation or onboarding, you can choose whether to start Zaya on sign-in. This uses standard per-user registry registration (<code>HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run</code>). It can be enabled or disabled anytime in Zaya Settings.</p>
"""
    },

    "android-installation": {
        "title": "Android Companion Installation",
        "description": "Installing Zaya Companion APK, permissions overview, and local pairing.",
        "html": """
<h1>Android Companion Installation</h1>
<p>The <b>Zaya Companion</b> application connects your Android smartphone to your laptop runtime. It allows you to speak to Zaya, receive proactive alerts, mirror notifications, and handle cellular phone calls remotely.</p>

<h2>Installation Options</h2>
<ul>
  <li><b>Google Play Store</b>: Submission track in progress (pre-launch testing).</li>
  <li><b>Direct Official APK</b>: Download the cryptographically signed release APK directly from <a href="/download">zaya.sajan.codes/download</a> or the official <a href="https://github.com/sajancodes/zaya-companion-releases/releases/latest" target="_blank" rel="noopener">GitHub Releases channel</a>.</li>
</ul>

<h2>Sideloading the APK</h2>
<ol>
  <li>Download <code>Zaya-Companion.apk</code> on your Android phone.</li>
  <li>Tap the downloaded file. If prompted, allow "Install unknown apps" for your browser or file manager.</li>
  <li>Review requested permissions and tap <b>Install</b>.</li>
  <li>Open Zaya Companion and enter your laptop's local IP address (or scan the pairing QR displayed on your desktop).</li>
</ol>

<h2>Permissions Audit</h2>
<ul>
  <li><b>Microphone (RECORD_AUDIO)</b>: Captures voice commands when conversing with Zaya.</li>
  <li><b>Phone & Call State (READ_PHONE_STATE, CALL_PHONE)</b>: Allows Zaya to identify incoming callers and manage cellular calls on your behalf.</li>
  <li><b>Foreground Service</b>: Keeps audio connection alive when phone screen is locked.</li>
  <li><b>Notifications (POST_NOTIFICATIONS)</b>: Alerts you of reminders and incoming call status.</li>
</ul>
"""
    },

    "virtual-keyboard": {
        "title": "Virtual Gesture Keyboard Guide",
        "description": "Operating the optical hand-tracking virtual keyboard with mid-air gesture typing.",
        "html": """
<h1>Virtual Gesture Keyboard Guide</h1>
<p>Zaya features a mid-air virtual keyboard powered by isolated MediaPipe hand landmark tracking. You can type in any Windows text field without touching physical peripherals.</p>

<h2>How It Works</h2>
<ol>
  <li><b>Open Vision Control Center</b>: Click the camera icon on the Zaya HUD or speak <i>"Open hand keyboard"</i>.</li>
  <li><b>Hold Up Your Hand</b>: Position your hand approximately 30 to 70 cm in front of the webcam.</li>
  <li><b>Target Keys</b>: Extend your index finger. A glowing holographic targeting cursor tracks your fingertip over the on-screen keyboard overlay.</li>
  <li><b>Poke to Type</b>: Push your finger forward toward the camera. When your fingertip crosses the palm-relative depth threshold, the key triggers with a gentle click.</li>
  <li><b>Retract & Next Key</b>: Pull your finger back past the release threshold to arm the next keystroke.</li>
</ol>

<h2>Key Safeguards</h2>
<div class="callout">
  <b>Anti-Self-Typing Guard:</b> Zaya automatically detects when its own window or sensitive system password prompts are active, and suppresses virtual keyboard key injection to prevent self-entry loops.
</div>
<ul>
  <li><b>Palm-Relative Depth Invariance</b>: Depth is measured relative to your palm plane, so leaning forward or backward does not shift the press trigger point.</li>
  <li><b>Hysteresis Latch</b>: A pressed key remains locked until you retract your finger, eliminating double-press stutter.</li>
</ul>
"""
    },

    "spatial-workspace": {
        "title": "Spatial 3D Workspace Guide",
        "description": "Generating, inspecting, and manipulating interactive 3D mechanical schematics.",
        "html": """
<h1>Spatial 3D Workspace Guide</h1>
<p>The Spatial Workspace generates interactive 3D engineering schematics that you can inspect, rotate, explode, and slice in real time.</p>

<h2>Opening the Workspace</h2>
<p>Say <i>"Open spatial workspace"</i> or click the 3D cube icon on the Zaya HUD. An interactive Three.js window opens alongside your workspace.</p>

<h2>Core Spatial Commands</h2>
<ul>
  <li><b>Generation</b>: Say <i>"Generate an inline 4-cylinder engine"</i>, <i>"Show a jet turbine"</i>, <i>"Render a motherboard"</i>, or <i>"Create a robotic arm"</i>.</li>
  <li><b>Component Explosion</b>: Say <i>"Explode components"</i>. Zaya calculates functional radial displacement vectors and smoothly separates every part along its mechanical axis.</li>
  <li><b>Cross-Section Slicing</b>: Say <i>"Slice on the X plane"</i> or <i>"Cut through the middle"</i> to expose internal pistons, bearings, and fluid channels.</li>
  <li><b>Inspection & Undo</b>: Click or point to any component to highlight its metadata. Say <i>"Undo"</i> to revert the last manipulation.</li>
</ul>

<div class="callout">
  <b>Note:</b> Spatial schematics are semantic illustrative models designed for spatial visualization, education, and conceptual understanding.
</div>
"""
    },

    "voice": {
        "title": "Voice Interaction & Audio Configuration",
        "description": "Configuring microphones, speakers, push-to-talk, and Live voices.",
        "html": """
<h1>Voice Interaction & Audio Control</h1>
<p>Zaya's voice pipeline connects to Gemini Live bidirectional audio streaming for conversational responsiveness.</p>

<h2>Voice Activation Modes</h2>
<ul>
  <li><b>Continuous Listening</b>: Zaya listens while the session is active and responds to natural speech.</li>
  <li><b>Push-to-Talk</b>: Hold your configured hotkey to speak; the microphone is instantly closed when released.</li>
  <li><b>Wake Word</b>: Sleeps until it hears <i>"Hey Jarvis"</i> or <i>"Zaya"</i>.</li>
</ul>

<h2>Available Voices</h2>
<p>Zaya supports official Live voices: <b>Nika</b> (default), <b>Puck</b>, <b>Charon</b>, <b>Kore</b>, <b>Fenrir</b>, and <b>Aoede</b>. Switch anytime from settings or by asking Zaya directly.</p>
"""
    },

    "vision": {
        "title": "Vision Control Center & Screen Perception",
        "description": "Screen diff tracking, native Windows OCR, and camera privacy principles.",
        "html": """
<h1>Vision Control Center & Screen Perception</h1>
<p>The Vision Control Center manages optical inputs and screen awareness while enforcing user privacy.</p>

<h2>Screen Perception Principles</h2>
<ul>
  <li><b>No Screenshot Clutter</b>: Zaya streams bitmap regions directly to Windows native OCR via memory pipes. Temporary screenshot files are never saved to disk.</li>
  <li><b>Differential Frame Tracking</b>: Perception only activates when screen content changes, keeping CPU usage below 1%.</li>
  <li><b>Camera Isolation</b>: Webcams are never accessed in the background. The camera is OFF at normal startup and activates only when hand controls or vision tools are explicitly opened.</li>
</ul>
"""
    },

    "phone-pairing": {
        "title": "Phone Pairing & Remote Call Handling",
        "description": "Connecting the Android Companion to desktop Zaya.",
        "html": """
<h1>Phone Pairing & Cellular Integration</h1>
<p>Pairs your Android smartphone to Zaya desktop over your home Wi-Fi or secure encrypted tunnel.</p>

<h2>How to Pair</h2>
<ol>
  <li>Ensure your phone and laptop are connected to the same Wi-Fi network.</li>
  <li>Open Zaya on your desktop and navigate to <b>Phone Companion Settings</b>.</li>
  <li>Open <b>Zaya Companion</b> on your phone and tap <b>Pair New Desktop</b>.</li>
  <li>Scan the QR code or enter the local IP address displayed on your desktop.</li>
</ol>
"""
    },

    "whatsapp": {
        "title": "Safe WhatsApp Integration",
        "description": "Voice message alerts, activity status, and owner-only authorization gate.",
        "html": """
<h1>Safe WhatsApp Integration</h1>
<p>Zaya connects to WhatsApp with strict privacy safeguards:</p>
<ul>
  <li><b>Activity-Only Context</b>: Auto-replies use only the owner's current activity (e.g. current song or active project); full private chat history is never exposed to LLMs.</li>
  <li><b>Owner Voice Alerts</b>: Urgent messages and explicit pass-along requests are spoken aloud to the owner.</li>
  <li><b>No Remote Code Execution</b>: External WhatsApp messages cannot trigger desktop commands.</li>
</ul>
"""
    },

    "automation": {
        "title": "Scheduled Automations & Background Tasks",
        "description": "Creating recurring reminders, system tasks, and background automations.",
        "html": """
<h1>Scheduled Automations & Background Tasks</h1>
<p>Zaya includes a persistent scheduler for background automations and morning briefings.</p>
<h2>Examples</h2>
<ul>
  <li><i>"Remind me every weekday at 9 AM to check deployment logs."</i></li>
  <li><i>"Run morning briefing every morning at 8:00 AM."</i></li>
  <li><i>"Check for desktop updates daily."</i></li>
</ul>
"""
    },

    "troubleshooting": {
        "title": "Troubleshooting & Problem Resolution",
        "description": "Solutions for API key errors, audio issues, SmartScreen warnings, and camera freeze.",
        "html": """
<h1>Troubleshooting Guide</h1>
<p>Solutions for common questions and setup issues:</p>

<h2>1. "Invalid API Key" or Connection Rejected</h2>
<p>Verify that you copied the complete key starting with <code>AIzaSy...</code> from <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener">Google AI Studio</a>. Check that your Google Cloud project has Generative Language API enabled.</p>

<h2>2. Windows SmartScreen Warning</h2>
<p>When running a newly published <code>ZayaSetup.exe</code>, Windows Defender SmartScreen may display <i>"Windows protected your PC"</i> because community download volume is newly building. Click <b>More info</b> and then <b>Run anyway</b>.</p>

<h2>3. Microphone Not Picking Up Voice</h2>
<p>Check Windows Settings &gt; Privacy &amp; Security &gt; Microphone, and confirm that desktop apps are allowed to access your microphone. Press <b>F4</b> to verify that Zaya is not muted.</p>

<h2>4. Webcam / Hand Tracking Stuck on STARTING</h2>
<p>Confirm that another application (Zoom, Teams, Discord) is not locking the webcam exclusively. Close other camera apps and restart Vision Control Center.</p>
"""
    },

    "uninstall": {
        "title": "Uninstalling Zaya",
        "description": "Complete removal instructions and user data management.",
        "html": """
<h1>Uninstalling Zaya</h1>
<p>Zaya provides a clean uninstaller that removes application binaries while offering you the choice to preserve or erase your local memory and configurations.</p>

<h2>How to Uninstall</h2>
<ol>
  <li>Open Windows <b>Settings &gt; Apps &gt; Installed Apps</b>.</li>
  <li>Locate <b>Zaya</b> in the list.</li>
  <li>Click the three dots and select <b>Uninstall</b>.</li>
  <li>The uninstaller will ask: <i>"Would you like to remove your local Zaya data (memory, logs, cached models) as well?"</i>
    <ul>
      <li>Select <b>No</b> if you wish to keep your configurations and local databases for future installations.</li>
      <li>Select <b>Yes</b> to completely delete <code>%LOCALAPPDATA%\\Zaya</code> and leave zero traces on your system.</li>
    </ul>
  </li>
</ol>
"""
    },
}
