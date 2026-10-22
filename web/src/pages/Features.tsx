import React from 'react';

export const Features: React.FC = () => {
  return (
    <section className="section" style={{ paddingTop: '50px' }}>
      <div className="container">
        <div className="section-header">
          <div className="hero-tag">Capabilities</div>
          <h1 className="section-title">Architected for Genuine Autonomy</h1>
          <p className="section-desc">
            Every feature in Zaya is designed with deep OS integration, strict privacy boundaries, and isolated execution.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '40px', maxWidth: '900px', margin: '0 auto' }}>
          {/* Voice */}
          <div className="card" style={{ padding: '32px' }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>🎙️</div>
            <h2 style={{ fontSize: '22px', color: '#ffffff', marginBottom: '10px' }}>
              Conversational Voice & Live Streaming
            </h2>
            <p className="card-text">
              Zaya connects directly to Gemini Live bidirectional WebSocket audio streams. Speak naturally, interrupt anytime, and hear instant responses.
            </p>
            <ul style={{ margin: '16px 0 0 20px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              <li>• Push-to-talk chord and local wake-word ("Hey Jarvis" / "Zaya") gating</li>
              <li>• Acoustic echo cancellation and device selection for input/output</li>
              <li>• Proactive morning briefing and reminders integration</li>
            </ul>
          </div>

          {/* Vision */}
          <div className="card" style={{ padding: '32px' }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>👁️</div>
            <h2 style={{ fontSize: '22px', color: '#ffffff', marginBottom: '10px' }}>
              Vision Control Center & Screen Perception
            </h2>
            <p className="card-text">
              Provides screen awareness without saving clutter. Zaya tracks active application windows, monitors dialogs, inspects code errors, and translates visual contexts into structured action arguments.
            </p>
            <ul style={{ margin: '16px 0 0 20px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              <li>• Windows Native OCR via direct stdin byte streaming (no temporary PNGs on disk)</li>
              <li>• Region-of-interest differential frame change detection</li>
              <li>• Camera stays completely <b>OFF</b> at normal startup; optical perception is 100% opt-in</li>
            </ul>
          </div>

          {/* Hand tracking & keyboard */}
          <div className="card" style={{ padding: '32px' }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>🖐️ ⌨️</div>
            <h2 style={{ fontSize: '22px', color: '#ffffff', marginBottom: '10px' }}>
              Optical Hand Tracking & Virtual Keyboard
            </h2>
            <p className="card-text">
              Operate your computer in mid-air. Uses official Google MediaPipe Hand Landmarker weights running inside an isolated child worker (<code>ZayaHandWorker.exe</code>).
            </p>
            <ul style={{ margin: '16px 0 0 20px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              <li>• Palm-relative depth normalization: typing depth threshold adapts automatically as your hand moves closer or further from the webcam</li>
              <li>• Forward-pointing index finger poke latching with strict retraction hysteresis preventing accidental double-key presses</li>
              <li>• Security safeguard: refuses to inject keystrokes into Zaya's own window or credential dialogs</li>
            </ul>
          </div>

          {/* Spatial 3D */}
          <div className="card" style={{ padding: '32px' }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>🧊</div>
            <h2 style={{ fontSize: '22px', color: '#ffffff', marginBottom: '10px' }}>
              Spatial 3D Workspace
            </h2>
            <p className="card-text">
              Generate, visualize, and interact with complex 3D mechanical and electronic schematics in an isolated Three.js web environment.
            </p>
            <ul style={{ margin: '16px 0 0 20px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              <li>• Procedural generators for inline engines, turbines, gearboxes, motherboards, and battery packs</li>
              <li>• Semantic component explosion: disassemble parts radially along their functional mechanical axes</li>
              <li>• Custom cutting plane slicing, spatial part annotations, and undo/redo transaction history</li>
            </ul>
          </div>

          {/* Android Companion */}
          <div className="card" style={{ padding: '32px' }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>📱</div>
            <h2 style={{ fontSize: '22px', color: '#ffffff', marginBottom: '10px' }}>
              Android Companion Integration
            </h2>
            <p className="card-text">
              Extend Zaya to your smartphone. The companion application connects over your home Wi-Fi network or secure tunnel to your laptop runtime.
            </p>
            <ul style={{ margin: '16px 0 0 20px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              <li>• Incoming cellular call caller ID lookup and voice call answering on behalf of the owner</li>
              <li>• Mobile notification pass-along and voice command routing</li>
              <li>• No API keys or conversation history preloaded onto the phone</li>
            </ul>
          </div>

          {/* Security & WhatsApp */}
          <div className="card" style={{ padding: '32px' }}>
            <div style={{ fontSize: '32px', marginBottom: '12px' }}>🛡️</div>
            <h2 style={{ fontSize: '22px', color: '#ffffff', marginBottom: '10px' }}>
              Security, DPAPI Key Vault & WhatsApp Gate
            </h2>
            <p className="card-text">
              Built with an owner-centric security architecture. External web requests and contacts cannot trigger privileged commands.
            </p>
            <ul style={{ margin: '16px 0 0 20px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              <li>• Windows DPAPI local key encryption: API keys cannot be read by another Windows account or exported to another machine</li>
              <li>• WhatsApp integration: replies use current owner activity (current song/project); full chat history is never sent to models</li>
              <li>• Real confirmation gate: system commands, deletions, and file modifications require explicit owner authorization</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
};
