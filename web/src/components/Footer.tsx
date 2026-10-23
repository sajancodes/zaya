import React from 'react';

interface FooterProps {
  navigate: (path: string) => void;
}

export const Footer: React.FC<FooterProps> = ({ navigate }) => {
  return (
    <footer
      style={{
        position: 'relative',
        backgroundColor: '#020407',
        borderTop: '1px solid rgba(73, 223, 255, 0.12)',
        paddingTop: '80px',
        paddingBottom: '50px',
        overflow: 'hidden'
      }}
    >
      {/* Visual Destiny Trail fading into the distance */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: '2px',
          height: '60px',
          background: 'linear-gradient(to bottom, rgba(73, 223, 255, 0.8), rgba(73, 223, 255, 0))',
          boxShadow: '0 0 12px #49DFFF'
        }}
      />

      <div
        className="container"
        style={{
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '0 24px'
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '40px',
            marginBottom: '60px'
          }}
        >
          {/* Brand Col */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <img
                src="/assets/zaya-logo.png"
                alt="Zaya Brand Mark"
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  boxShadow: '0 0 12px rgba(95, 234, 255, 0.4)',
                  border: '1px solid rgba(95, 234, 255, 0.3)'
                }}
              />
              <span style={{ fontSize: '20px', fontWeight: 700, letterSpacing: '3px', color: '#F4FAFF' }}>
                ZAYA
              </span>
            </div>
            <p style={{ margin: 0, fontSize: '13px', color: '#8392A6', lineHeight: '1.6' }}>
              A personal AI system built to move with you. Conversational voice, computer operation, screen perception, optical hand control, and spatial workspace.
            </p>
            <p style={{ margin: 0, fontSize: '12px', color: '#DDFBFF', opacity: 0.8 }}>
              Created and developed by <strong>Sajan Rai</strong>.
            </p>
          </div>

          {/* System & Product */}
          <div>
            <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: '16px' }}>
              System
            </h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <li>
                <a href="/features" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Features Encyclopedia
                </a>
              </li>
              <li>
                <a href="/docs/voice" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Voice Architecture (Nika)
                </a>
              </li>
              <li>
                <a href="/docs/computer-control" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Desktop Operator & UIA
                </a>
              </li>
              <li>
                <a href="/docs/hand-control" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Optical Hand Tracking
                </a>
              </li>
              <li>
                <a href="/docs/spatial" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Spatial 3D Canvas
                </a>
              </li>
              <li>
                <a href="/docs/mobile" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Android Companion App
                </a>
              </li>
            </ul>
          </div>

          {/* Documentation */}
          <div>
            <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: '16px' }}>
              Documentation
            </h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <li>
                <a href="/docs/getting-started" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Getting Started Walkthrough
                </a>
              </li>
              <li>
                <a href="/docs/install-windows" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Windows Installation
                </a>
              </li>
              <li>
                <a href="/docs/providers" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  AI Provider Setup
                </a>
              </li>
              <li>
                <a href="/docs/local-ai" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Local AI Engine (Ollama/llama.cpp)
                </a>
              </li>
              <li>
                <a href="/docs/architecture" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Architecture Explorer
                </a>
              </li>
              <li>
                <a href="/docs/troubleshooting" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Troubleshooting & Diagnostics
                </a>
              </li>
            </ul>
          </div>

          {/* Platform & Trust */}
          <div>
            <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: '16px' }}>
              Platform & Trust
            </h4>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              <li>
                <a href="/download" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Download Zaya (v0.5.0)
                </a>
              </li>
              <li>
                <a href="/releases" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Official Releases & Notes
                </a>
              </li>
              <li>
                <a href="/roadmap" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Evolution Roadmap
                </a>
              </li>
              <li>
                <a href="/security" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Security & Trust Boundary
                </a>
              </li>
              <li>
                <a href="/privacy" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Privacy & Data Retention
                </a>
              </li>
              <li>
                <a href="/terms" style={{ color: '#8392A6', cursor: 'pointer' }}>
                  Terms & Open Attribution
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Crystal Accent Divider */}
        <div className="crystal-divider" style={{ margin: '40px 0 30px' }}>
          <span>◇</span>
        </div>

        {/* Bottom Bar with off-screen destiny line */}
        <div
          style={{
            borderTop: '1px solid rgba(73, 223, 255, 0.08)',
            paddingTop: '32px',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px'
          }}
        >
          <div style={{ fontSize: '12px', color: '#8392A6' }}>
            © {new Date().getFullYear()} Zaya. Created and developed by <strong>Sajan Rai</strong>. All rights reserved.
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '20px', fontSize: '12px' }}>
            <a
              href="https://github.com/sajancodes/zaya"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#8392A6', textDecoration: 'none' }}
            >
              GitHub (sajancodes/zaya)
            </a>
            <a
              href="https://github.com/sajancodes/zaya-companion-releases"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#8392A6', textDecoration: 'none' }}
            >
              Releases Portal
            </a>
            <span
              onClick={() => navigate('/about')}
              style={{ color: '#8392A6', cursor: 'pointer' }}
            >
              Founder Story
            </span>
          </div>
        </div>

        {/* Final trailing path line */}
        <div
          style={{
            marginTop: '40px',
            textAlign: 'center',
            fontSize: '11px',
            letterSpacing: '2px',
            textTransform: 'uppercase',
            color: 'rgba(73, 223, 255, 0.5)',
            fontFamily: "'JetBrains Mono', monospace"
          }}
        >
          Zaya is unfinished by design. The future continues.
          <div
            style={{
              width: '1px',
              height: '35px',
              background: 'linear-gradient(to bottom, rgba(73, 223, 255, 0.5), transparent)',
              margin: '12px auto 0 auto'
            }}
          />
        </div>
      </div>
    </footer>
  );
};
