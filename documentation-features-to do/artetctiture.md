Do it on python cause i have made some features so 
SYSTEM ARCHITECTURE.
IRIS maps natural audio input directly into OS-level instructions. Explore the neural execution cycle, process isolation boundary, and complete system stack.

Execution Pipeline
Split-Process Isolation
Secure IPC Bridge
Real-Time Voice-To-System Pipeline
IRIS establishes a persistent full-duplex WebRTC connection with Gemini Live. Audio streams continuously; when intent is matched, the state-machine locks and executes actions, feeding the output instantly back as audio.

01
WebRTC Audio Stream
User Speech Input
Persistent bidirectional live stream (<500ms latency).
02
Gemini 3.1 Live API
Intent Recognition & Parsing
Processes speech, outputs structured function call payloads.
03
LangGraph State Machine
Cyclic Tool Selection
Protected backend process orchestrates required system operations.
04
Native OS Execution
Protected Tools System
Nut.js cursor events, CLI executions, filesystem operations take action.
05
Feedback Synthesis
Audio & UI Update Loop
System output returned to Gemini Live; synthesizes response back to speaker.
Technical Stack Inventory
Core Desktop & UI Framework
Electron & Vite
High-performance desktop compilation & fast bundler lifecycle.
React 19
Component-based, optimized virtual DOM frontend engine.
Tailwind CSS v4
Utility-first styling matching modern HSL palettes.
Framer Motion & GSAP
Hardware-accelerated animations and scroll synchronization.
Three.js & React Three Fiber
3D neural network visualizers and active orb renderers.
Zustand
Lightweight, centralized state management.
AI & Neural Orchestration Layer
Gemini 3.1 Live API
Bidirectional real-time WebRTC audio stream + vision intelligence.
Google GenAI SDK
Multimodal structured reasoning, function-calling & JSON schemas.
LangGraph
Agentic state loop orchestration & cyclic tool selectors (Protected).
LanceDB
High-speed local vector database for persistent RAG and memory.
OS Control & Automation
Nut.js
Native OS mouse coordinate targeting, keyboard typing injection.
Puppeteer & Stealth
Headless browser scraping, automated form fill, web agent.
Node Window Manager
Active application window resizing, repositioning, and alignment.
Tesseract.js
Optical Character Recognition (OCR) for screen peeling code extraction.
Frontend Render Process
The frontend operates as a standard Chromium view. It is completely isolated and lacks direct access to the Node.js runtime or direct filesystem endpoints.

React 19 UI & Zustand Stores
Three.js WebGL & Audio Nodes
Preload secure scripts injection
Backend Main Process
Protected
The main process executes system operations. It compiles directly into binary V8 bytecode, meaning reverse engineering requires substantial resources.

LangGraph Voice Orchestration
Active OS Automation (Nut.js/Shell)
ASAR Hashing & local keystore logic
Secure Context-Isolated IPC Tunnel
Frontend render frames trigger tools through a strict, whitelisted Inter-Process Communication (IPC) bridge. No direct Node calls are made in client modules.

IPC Bridge Signature
ipc-bridge.ts
// 1. FRONTEND CALL (React Component)
const handleAction = async (payload: { tool: string; args: any }) => {
  try {
    // Invoke secure channel without exposure to direct require/electron elements
    const result = await window.electron.ipcRenderer.invoke('execute-tool', payload);
    console.log("OS Execution complete:", result);
  } catch (error) {
    console.error("Action execution blocked:", error);
  }
};

// 2. PRELOAD SCRIPTS (Isolated bridge contract)
import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electron', {
  ipcRenderer: {
    invoke: (channel: string, data: any) => {
      // Validate channel name to prevent access injection
      const whitelistedChannels = ['execute-tool', 'system-telemetry', 'auth-keychain'];
      if (whitelistedChannels.includes(channel)) {
        return ipcRenderer.invoke(channel, data);
      }
      return Promise.reject(new Error("Unauthorized IPC channel call blocked"));
    }
  }
});

// 3. BACKEND HANDLER (Obfuscated & compiled inside V8 bytecode main process)
ipcMain.handle('execute-tool', async (event, { tool, args }) => {
  // Validate token signature and run internal LangGraph decision cycle
  const result = await LangGraphRunner.trigger(tool, args);
  return result;
});