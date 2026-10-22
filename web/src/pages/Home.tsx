import React from 'react';

interface HomeProps {
  navigate: (path: string) => void;
  latestVersion?: string;
}

export const Home: React.FC<HomeProps> = ({ navigate, latestVersion = '0.5.0' }) => {
  return (
    <>
      {/* Hero Section */}
      <section className="hero">
        <div className="container">
          <div className="hero-tag">Spatial Intelligence · Autonomous Assistant</div>
          <h1 className="hero-title">
            Your Personal AI Assistant.<br />
            Spatial. Private. Autonomous.
          </h1>
          <p className="hero-subtitle">
            Zaya unites real-time conversational voice, desktop screen perception, optical hand tracking,
            depth-invariant virtual keyboard typing, and an interactive 3D spatial workspace into a single private desktop application.
          </p>

          <div className="hero-actions">
            <a
              href="/download/windows"
              className="btn btn-primary btn-large"
              onClick={() => {
                // Record download event automatically
                fetch('/api/downloads/event', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ platform: 'windows', version: latestVersion }),
                }).catch(() => {});
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.949-1.801" />
              </svg>
              Download for Windows
            </a>
            <button
              className="btn btn-secondary btn-large"
              onClick={() => navigate('/download')}
            >
              Explore Platforms
            </button>
          </div>

          <div className="hero-badges">
            <span>✓ Windows 10/11 (64-bit)</span>
            <span>✓ Android Companion App</span>
            <span>✓ Local DPAPI Key Encryption</span>
            <span>✓ Latest: Zaya v{latestVersion}</span>
          </div>
        </div>
      </section>

      {/* Core Capabilities Grid */}
      <section className="section" style={{ backgroundColor: 'var(--bg-surface)', borderTop: '1px solid var(--border-subtle)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div className="container">
          <div className="section-header">
            <h2 className="section-title">Built for Real Desktop Intelligence</h2>
            <p className="section-desc">
              Not a chat wrapper. Zaya runs deep operating system tools, perception pipelines, and local neural workers.
            </p>
          </div>

          <div className="grid-3">
            <div className="card">
              <div className="card-icon">🎙️</div>
              <h3 className="card-title">Real-Time Voice Stream</h3>
              <p className="card-text">
                Direct conversational voice powered by Gemini Live audio streaming. Interruptible, low-latency responses with wake-word and push-to-talk support.
              </p>
            </div>

            <div className="card">
              <div className="card-icon">👁️</div>
              <h3 className="card-title">Vision Control Center</h3>
              <p className="card-text">
                Continuous desktop screen perception and OCR with zero screenshot clutter. Understands active windows, monitors dialogs, and inspects errors.
              </p>
            </div>

            <div className="card">
              <div className="card-icon">🖐️</div>
              <h3 className="card-title">Optical Hand Tracking</h3>
              <p className="card-text">
                Isolated MediaPipe hand landmark inference in a dedicated child worker. Real-time 21-point tracking running at 30 FPS without blocking the UI.
              </p>
            </div>

            <div className="card">
              <div className="card-icon">⌨️</div>
              <h3 className="card-title">Virtual Gesture Keyboard</h3>
              <p className="card-text">
                Mid-air typing with palm-relative depth invariance. Deliberate poke latching, key retract hysteresis, and strict security guards preventing self-entry.
              </p>
            </div>

            <div className="card">
              <div className="card-icon">🧊</div>
              <h3 className="card-title">Spatial 3D Workspace</h3>
              <p className="card-text">
                Interactive Three.js 3D mechanical schematics. Inspect components, trigger semantic component explosion, annotate parts, and slice cross-sections.
              </p>
            </div>

            <div className="card">
              <div className="card-icon">📱</div>
              <h3 className="card-title">Android Companion</h3>
              <p className="card-text">
                Continuous phone connectivity over local Wi-Fi or encrypted tunnel. Mirrors cellular calls, performs caller ID lookup, and supports mobile voice control.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="section" style={{ textAlign: 'center' }}>
        <div className="container">
          <h2 className="section-title">Get Started with Zaya</h2>
          <p className="section-desc" style={{ marginBottom: '32px' }}>
            Download ZayaSetup.exe, follow the first-run onboarding wizard, and connect your Google AI Studio key.
          </p>
          <button className="btn btn-primary btn-large" onClick={() => navigate('/download')}>
            Download Now
          </button>
        </div>
      </section>
    </>
  );
};
