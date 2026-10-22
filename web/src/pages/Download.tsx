import React, { useState } from 'react';
import { RELEASES_DATA } from '../data/releases';

interface DownloadProps {
  navigate: (path: string) => void;
}

export const Download: React.FC<DownloadProps> = ({ navigate }) => {
  const [copiedSha, setCopiedSha] = useState<string | null>(null);

  const windowsRelease = RELEASES_DATA.find((r) => r.platform === 'windows') || RELEASES_DATA[0];
  const androidRelease = RELEASES_DATA.find((r) => r.platform === 'android') || RELEASES_DATA[1];

  const handleCopySha = (sha: string) => {
    navigator.clipboard.writeText(sha);
    setCopiedSha(sha);
    setTimeout(() => setCopiedSha(null), 2500);
  };

  return (
    <section className="section" style={{ minHeight: '100vh', paddingTop: '60px' }}>
      <div className="container" style={{ maxWidth: '1040px' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 60px auto' }}>
          <div className="section-label">Distribution Portal</div>
          <h1 className="editorial-title" style={{ fontSize: '48px', marginBottom: '16px' }}>
            Download Zaya for Your Environment
          </h1>
          <p style={{ color: '#8392A6', fontSize: '16px', lineHeight: '1.7' }}>
            Official verified release binaries for Windows desktop and native Android companion. Free, privacy-first, and zero telemetry without your consent.
          </p>
        </div>

        {/* Primary Download Cards: Windows & Android */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
            gap: '30px',
            marginBottom: '60px'
          }}
        >
          {/* Windows Desktop Card */}
          <div className="glass-panel" style={{ padding: '36px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span className="badge badge-stable">STABLE · v{windowsRelease.version}</span>
                <span style={{ fontSize: '12px', color: '#8392A6' }}>{windowsRelease.sizeFormatted}</span>
              </div>

              <h2 style={{ fontSize: '24px', color: '#F4FAFF', fontWeight: 600, marginBottom: '8px' }}>
                Windows Desktop
              </h2>
              <p style={{ color: '#8392A6', fontSize: '14px', lineHeight: '1.6', marginBottom: '24px' }}>
                Complete desktop runtime uniting Gemini Live voice, screen perception, optical hand tracking, and 3D spatial intelligence.
              </p>

              <div style={{ marginBottom: '24px' }}>
                <a
                  href="/download/windows"
                  className="btn btn-primary btn-large"
                  style={{ width: '100%', boxSizing: 'border-box' }}
                  onClick={() => {
                    fetch('/api/downloads/event', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ platform: 'windows', version: windowsRelease.version })
                    }).catch(() => {});
                  }}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.949-1.801" />
                  </svg>
                  Download {windowsRelease.filename}
                </a>
              </div>

              {/* SHA256 Verification */}
              <div
                style={{
                  padding: '12px',
                  backgroundColor: 'rgba(8, 20, 35, 0.6)',
                  borderRadius: '6px',
                  border: '1px solid rgba(73, 223, 255, 0.1)',
                  fontSize: '11px',
                  marginBottom: '20px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8392A6', marginBottom: '4px' }}>
                  <span>SHA-256 Checksum:</span>
                  <span
                    onClick={() => handleCopySha(windowsRelease.sha256)}
                    style={{ color: '#49DFFF', cursor: 'pointer' }}
                  >
                    {copiedSha === windowsRelease.sha256 ? '✓ Copied' : 'Copy'}
                  </span>
                </div>
                <code style={{ wordBreak: 'break-all', fontSize: '10px', color: '#DDFBFF' }}>
                  {windowsRelease.sha256}
                </code>
              </div>
            </div>

            <div>
              <div style={{ fontSize: '12px', color: '#8392A6', borderTop: '1px solid rgba(73, 223, 255, 0.1)', paddingTop: '16px' }}>
                <strong style={{ color: '#DDFBFF' }}>Requirements:</strong> Windows 10/11 (64-bit), 8GB RAM, microphone.
              </div>
            </div>
          </div>

          {/* Android Companion Card */}
          <div className="glass-panel" style={{ padding: '36px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span className="badge badge-stable">STABLE · v{androidRelease.version}</span>
                <span style={{ fontSize: '12px', color: '#8392A6' }}>{androidRelease.sizeFormatted}</span>
              </div>

              <h2 style={{ fontSize: '24px', color: '#F4FAFF', fontWeight: 600, marginBottom: '8px' }}>
                Android Companion App
              </h2>
              <p style={{ color: '#8392A6', fontSize: '14px', lineHeight: '1.6', marginBottom: '24px' }}>
                Native Kotlin and Jetpack Compose companion. Two-way voice, priority phone ringing (P0/P1), live phone video context, and task views.
              </p>

              <div style={{ marginBottom: '24px' }}>
                <a
                  href="/download/android"
                  className="btn btn-secondary btn-large"
                  style={{ width: '100%', boxSizing: 'border-box' }}
                  onClick={() => {
                    fetch('/api/downloads/event', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ platform: 'android', version: androidRelease.version })
                    }).catch(() => {});
                  }}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17.523 15.3414c-.5511 0-.9993-.4486-.9993-.9997s.4482-.9993.9993-.9993c.551 0 .9993.4482.9993.9993.0001.5511-.4483.9997-.9993.9997m-11.046 0c-.5511 0-.9993-.4486-.9993-.9997s.4482-.9993.9993-.9993c.5511 0 .9993.4482.9993.9993 0 .5511-.4482.9997-.9993.9997m11.4045-6.02l1.9973-3.4592a.416.416 0 00-.1521-.5676.416.416 0 00-.5676.1521l-2.0223 3.503C15.5898 8.4239 13.847 8.134 12 8.134c-1.847 0-3.5898.2899-5.1368.8157L4.8409 5.4467a.4161.4161 0 00-.5677-.1521.4157.4157 0 00-.1521.5676l1.9973 3.4592C2.6889 11.1867.3432 14.6589 0 18.761h24c-.3432-4.1021-2.6889-7.5743-6.1185-9.4396" />
                  </svg>
                  Download {androidRelease.filename}
                </a>
              </div>

              {/* Pairing Tip */}
              <div
                style={{
                  padding: '12px',
                  backgroundColor: 'rgba(8, 20, 35, 0.6)',
                  borderRadius: '6px',
                  border: '1px solid rgba(73, 223, 255, 0.1)',
                  fontSize: '11px',
                  marginBottom: '20px'
                }}
              >
                <div style={{ color: '#DDFBFF', fontWeight: 600, marginBottom: '2px' }}>
                  Encrypted Keystore Pairing:
                </div>
                <div style={{ color: '#8392A6' }}>
                  Pair once via 6-character code in Settings & Controls → Remote Control. Credentials remain in local Android Hardware Keystore.
                </div>
              </div>
            </div>

            <div>
              <div style={{ fontSize: '12px', color: '#8392A6', borderTop: '1px solid rgba(73, 223, 255, 0.1)', paddingTop: '16px' }}>
                <strong style={{ color: '#DDFBFF' }}>Requirements:</strong> Android 10+ (API 29+), Wi-Fi connection to laptop.
              </div>
            </div>
          </div>
        </div>

        {/* First-Run Setup Walkthrough */}
        <div className="glass-panel" style={{ padding: '40px', marginBottom: '60px' }}>
          <h2 className="editorial-title" style={{ fontSize: '28px', color: '#F4FAFF', marginBottom: '16px' }}>
            First-Run Provider Configuration
          </h2>
          <p style={{ color: '#8392A6', fontSize: '14px', lineHeight: '1.7', marginBottom: '24px' }}>
            Zaya uses your own provider API credentials. Here is how to configure your free Gemini key in under 60 seconds:
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '16px',
              marginBottom: '24px'
            }}
          >
            {[
              { step: '1', title: 'Open Google AI Studio', desc: 'Visit aistudio.google.com/app/apikey and sign in with your Google account.' },
              { step: '2', title: 'Create API Key', desc: 'Click "Create API key" under any personal Google Cloud project.' },
              { step: '3', title: 'Paste into Zaya', desc: 'Open Zaya onboarding window and paste your key into the masked field.' },
              { step: '4', title: 'Hardware DPAPI Vault', desc: 'Zaya encrypts the key with Windows DPAPI before writing to disk.' }
            ].map((s) => (
              <div key={s.step} style={{ padding: '16px', backgroundColor: 'rgba(8, 20, 35, 0.6)', borderRadius: '8px', border: '1px solid rgba(73, 223, 255, 0.12)' }}>
                <div style={{ color: '#49DFFF', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  STEP {s.step}
                </div>
                <div style={{ color: '#F4FAFF', fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>{s.title}</div>
                <div style={{ color: '#8392A6', fontSize: '12px', lineHeight: '1.5' }}>{s.desc}</div>
              </div>
            ))}
          </div>

          <a
            href="https://aistudio.google.com/app/apikey"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
          >
            Open Google AI Studio ↗
          </a>
        </div>

        {/* Source Installation Option */}
        <div style={{ textAlign: 'center' }}>
          <h3 style={{ fontSize: '18px', color: '#F4FAFF', marginBottom: '8px' }}>
            Looking to Build from Source?
          </h3>
          <p style={{ color: '#8392A6', fontSize: '14px', marginBottom: '16px' }}>
            Clone the repository, inspect the architecture, or contribute to Zaya on GitHub.
          </p>
          <button onClick={() => navigate('/docs/install/source')} className="btn btn-secondary">
            View Source Setup Documentation →
          </button>
        </div>
      </div>
    </section>
  );
};
