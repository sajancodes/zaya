import React from 'react';

export const Privacy: React.FC = () => {
  return (
    <section className="section" style={{ paddingTop: '50px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div className="section-header">
          <div className="hero-tag">Transparency</div>
          <h1 className="section-title">Privacy Policy</h1>
          <p className="section-desc">
            Last Updated: October 2026 · Notice: Subject to owner and legal review before commercial operation.
          </p>
        </div>

        <div className="card" style={{ padding: '40px', fontSize: '15px', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          <h2 style={{ color: '#ffffff', fontSize: '20px', marginBottom: '12px' }}>1. Architecture Philosophy</h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya is created and developed by Sajan Rai with an uncompromising privacy-first design.
            Unlike cloud assistants that harvest your workspace and telemetry, Zaya runs as a local native application on your personal computer.
          </p>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>2. What Stays Strictly Local on Your Device</h2>
          <ul style={{ marginBottom: '20px', paddingLeft: '20px' }}>
            <li><b>Your AI API Keys</b>: Stored in <code>%LOCALAPPDATA%\Zaya\config\api_keys.json</code> and protected at rest using <b>Windows DPAPI</b>. Keys never touch Zaya telemetry servers.</li>
            <li><b>Webcam & Hand Tracking Frames</b>: Processed in real time at 30 FPS inside an isolated local process (<code>ZayaHandWorker.exe</code>). Video frames are analyzed ephemerally in RAM and instantly discarded. Zero frames or video clips are ever saved to disk or transmitted over the internet.</li>
            <li><b>Screen Perception & OCR</b>: Bitmap regions are inspected in-memory and piped directly into Windows native OCR. Temporary screenshot image files are never written to disk.</li>
            <li><b>Local Memories & Databases</b>: Your long-term memory, conversation summaries, and action logs are stored in a local SQLite database in <code>%LOCALAPPDATA%\Zaya\memory\</code>.</li>
            <li><b>WhatsApp & Messages</b>: WhatsApp auto-replies only use your active owner activity context (e.g. current project); chat history is stored locally in your linked browser session.</li>
          </ul>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>3. External Network Communications</h2>
          <p style={{ marginBottom: '12px' }}>Zaya communicates over the internet exclusively for two explicit purposes:</p>
          <ol style={{ marginBottom: '20px', paddingLeft: '20px' }}>
            <li><b>Your Chosen AI Provider</b>: Prompts, voice audio streams, and tool requests are sent directly to your selected provider (e.g. Google Gemini or OpenAI) using your own API key under your own provider terms.</li>
            <li><b>Official Updates</b>: Periodic HTTPS queries to <code>https://github.com/sajancodes/zaya-companion-releases/</code> to check for published <code>desktop-update.json</code> manifests.</li>
          </ol>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>4. Anonymous Installation & Heartbeat Telemetry</h2>
          <p style={{ marginBottom: '12px' }}>
            To understand how many installations are active and which versions are in use, Zaya includes minimal, privacy-preserving telemetry:
          </p>
          <ul style={{ marginBottom: '16px', paddingLeft: '20px' }}>
            <li><b>Cryptographically Random Installation ID</b>: A random UUIDv4 generated on first launch. It contains <b>zero</b> hardware serials, MAC addresses, CPU/GPU identifiers, or disk IDs.</li>
            <li><b>Platform & Version</b>: E.g. <code>"platform": "windows"</code>, <code>"version": "0.5.0"</code>.</li>
            <li><b>Heartbeat Frequency</b>: At most once every 24 hours.</li>
          </ul>

          <div className="callout">
            <b>What We NEVER Collect:</b> Zaya telemetry never records or transmits your API keys, prompts, conversations, voice recordings, webcam frames, screen captures, passwords, phone contacts, or private files.
          </div>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>5. Opt-Out Controls</h2>
          <p style={{ marginBottom: '20px' }}>
            You can disable anonymous usage statistics at any time during onboarding or by opening Zaya Settings and toggling off <i>"Share anonymous usage statistics"</i>. When disabled, no telemetry packets are sent.
          </p>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>6. Contact & Inquiries</h2>
          <p>
            For questions regarding Zaya privacy practices or to submit an inquiry, contact the developer at <code>ab4290025@gmail.com</code>.
          </p>
        </div>
      </div>
    </section>
  );
};
