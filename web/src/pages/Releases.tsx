import React, { useEffect, useState } from 'react';
import { ReleaseInfo } from '../types';

export const Releases: React.FC = () => {
  const [releases, setReleases] = useState<ReleaseInfo[]>([
    {
      version: '0.5.0',
      platform: 'windows',
      filename: 'ZayaSetup.exe',
      url: 'https://github.com/sajancodes/zaya-companion-releases/releases/download/v0.5.0/ZayaSetup.exe',
      sha256: 'fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1',
      size: 48500000,
      release_notes: `Zaya 0.5.0 Production Release:
• Vision Control Center with optical tracking
• Depth-invariant virtual keyboard mid-air typing
• Spatial 3D workspace with Three.js renderer
• Windows DPAPI local secret vault
• In-app background auto-updater`,
      published_at: 1729580000,
    },
    {
      version: '0.4.6',
      platform: 'android',
      filename: 'Zaya-Companion.apk',
      url: 'https://github.com/sajancodes/zaya-companion-releases/releases/download/android-0.4.6/Zaya-Companion.apk',
      sha256: 'e89c6295efb867c2105e4d293d07e6e5a6a6fa34d580ce6ffcf06d4493ecfa25',
      size: 24200000,
      release_notes: `Zaya Companion 0.4.6:
• Play Store install-source detection
• Dual-mode release tag compatibility
• Foreground service audio streaming stability
• Low-latency cellular call caller ID lookup`,
      published_at: 1729480000,
    },
  ]);

  useEffect(() => {
    fetch('/api/releases')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setReleases(data);
        }
      })
      .catch(() => {});
  }, []);

  return (
    <section className="section" style={{ paddingTop: '50px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div className="section-header">
          <div className="hero-tag">Changelog</div>
          <h1 className="section-title">Releases & Patch Notes</h1>
          <p className="section-desc">
            Track updates, improvements, and fixes across Zaya desktop and companion versions.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          {releases.map((rel) => (
            <div key={`${rel.platform}-${rel.version}`} className="card" style={{ padding: '32px' }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '12px',
                  flexWrap: 'wrap',
                  gap: '8px',
                }}
              >
                <div>
                  <h2 style={{ fontSize: '24px', color: '#ffffff', display: 'inline' }}>
                    Zaya v{rel.version}
                  </h2>
                  <span
                    style={{
                      marginLeft: '10px',
                      background: 'rgba(0, 212, 255, 0.12)',
                      color: 'var(--accent-cyan)',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                    }}
                  >
                    {rel.platform}
                  </span>
                </div>
                <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                  {new Date(rel.published_at * 1000).toLocaleDateString()}
                </span>
              </div>

              <div
                style={{
                  whiteSpace: 'pre-line',
                  color: 'var(--text-secondary)',
                  fontSize: '14px',
                  lineHeight: '1.6',
                  marginBottom: '20px',
                }}
              >
                {rel.release_notes}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
                <a href={rel.url} className="btn btn-primary" style={{ fontSize: '13px', padding: '8px 16px' }}>
                  Download {rel.filename}
                </a>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  SHA-256: {rel.sha256 ? `${rel.sha256.slice(0, 16)}...${rel.sha256.slice(-8)}` : 'Verified'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
