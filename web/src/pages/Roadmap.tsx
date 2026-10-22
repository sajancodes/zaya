import React from 'react';

export const Roadmap: React.FC = () => {
  return (
    <section className="section" style={{ paddingTop: '50px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div className="section-header">
          <div className="hero-tag">Development</div>
          <h1 className="section-title">Product Roadmap</h1>
          <p className="section-desc">
            Public development direction, completed milestones, and upcoming capabilities for Zaya.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
          {/* Shipped */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
              <span style={{ background: 'rgba(0, 255, 136, 0.2)', color: 'var(--accent-green)', padding: '4px 10px', borderRadius: '4px', fontWeight: 700, fontSize: '12px' }}>
                SHIPPED
              </span>
              <h2 style={{ fontSize: '20px', color: '#ffffff' }}>Completed Core Foundation</h2>
            </div>

            <div className="card">
              <ul style={{ listStyle: 'none', fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.8' }}>
                <li>✓ <b>Live Conversational Voice</b>: Gemini Live bidirectional audio WebSocket streaming.</li>
                <li>✓ <b>Vision Control Center</b>: Continuous screen diff detection, Windows native OCR without screenshot files.</li>
                <li>✓ <b>Isolated Hand Tracking</b>: Real-time 21-point MediaPipe hand tracking in child worker process.</li>
                <li>✓ <b>Virtual Gesture Keyboard</b>: Palm-relative depth-invariant mid-air typing with hysteresis safeguards.</li>
                <li>✓ <b>Spatial 3D Workspace</b>: Interactive Three.js schematics with radial component explosion and slicing.</li>
                <li>✓ <b>Android Companion Foundation</b>: Remote phone audio, caller ID lookup, and cellular call answering.</li>
                <li>✓ <b>Production Packaging</b>: Inno Setup Windows installer (<code>ZayaSetup.exe</code>) & Play Store AAB prep.</li>
                <li>✓ <b>Windows DPAPI Key Vault</b>: Encrypted API key storage at rest bound to the local Windows user account.</li>
              </ul>
            </div>
          </div>

          {/* In Progress */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
              <span style={{ background: 'rgba(0, 212, 255, 0.2)', color: 'var(--accent-cyan)', padding: '4px 10px', borderRadius: '4px', fontWeight: 700, fontSize: '12px' }}>
                IN PROGRESS
              </span>
              <h2 style={{ fontSize: '20px', color: '#ffffff' }}>Current Focus Areas</h2>
            </div>

            <div className="card">
              <ul style={{ listStyle: 'none', fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.8' }}>
                <li>🔄 <b>Google Play Store Production Track</b>: Finalizing developer verification and store review enrollment.</li>
                <li>🔄 <b>Windows Authenticode Reputation</b>: Establishing code signing certificates and SmartScreen trust.</li>
                <li>🔄 <b>Expanded Schematic Generator Library</b>: Adding procedural generator support for jet engines and robotics.</li>
                <li>🔄 <b>Multi-Monitor Perception</b>: Extending differential screen OCR across secondary and virtual displays.</li>
              </ul>
            </div>
          </div>

          {/* Planned */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
              <span style={{ background: 'rgba(255, 204, 0, 0.2)', color: '#ffcc00', padding: '4px 10px', borderRadius: '4px', fontWeight: 700, fontSize: '12px' }}>
                PLANNED
              </span>
              <h2 style={{ fontSize: '20px', color: '#ffffff' }}>Future Exploration</h2>
            </div>

            <div className="card">
              <ul style={{ listStyle: 'none', fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.8' }}>
                <li>⏳ <b>Cross-Device Spatial Canvas</b>: Synchronizing the 3D workspace with mobile AR and VR head-mounted displays.</li>
                <li>⏳ <b>Local Small Model Offline Fallbacks</b>: On-device quantized SLM execution when internet is disconnected.</li>
                <li>⏳ <b>Custom Macro Recorder</b>: Visual recording of desktop workflows with automated parameterization.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
