import React from 'react';

interface DownloadProps {
  navigate: (path: string) => void;
  windowsVersion?: string;
  androidVersion?: string;
}

export const Download: React.FC<DownloadProps> = ({
  navigate,
  windowsVersion = '0.5.0',
  androidVersion = '0.4.6',
}) => {
  const handleWindowsDownload = () => {
    fetch('/api/downloads/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: 'windows', version: windowsVersion }),
    }).catch(() => {});
    window.location.href = '/download/windows';
  };

  const handleAndroidDownload = () => {
    fetch('/api/downloads/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: 'android', version: androidVersion }),
    }).catch(() => {});
    window.location.href = '/download/android';
  };

  return (
    <section className="section" style={{ paddingTop: '50px' }}>
      <div className="container">
        <div className="section-header">
          <div className="hero-tag">Official Releases</div>
          <h1 className="section-title">Download Zaya</h1>
          <p className="section-desc">
            Choose your platform below. All official binaries are cryptographically signed and hash-verified.
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
            gap: '32px',
            maxWidth: '900px',
            margin: '0 auto 60px',
          }}
        >
          {/* Windows Card */}
          <div className="download-card primary">
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span style={{ fontSize: '24px' }}>🪟 Windows</span>
                <span style={{ background: 'rgba(0, 212, 255, 0.15)', color: 'var(--accent-cyan)', padding: '4px 10px', borderRadius: '4px', fontSize: '12px', fontWeight: 700 }}>
                  STABLE
                </span>
              </div>
              <h2 style={{ fontSize: '22px', color: '#ffffff', marginBottom: '8px' }}>Zaya for Windows</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
                Full desktop application with real-time voice, Vision Control Center, optical hand tracking, and 3D spatial workspace.
              </p>

              <ul style={{ listStyle: 'none', marginBottom: '28px', fontSize: '13px', color: 'var(--text-muted)' }}>
                <li style={{ marginBottom: '6px' }}>• Windows 10 / 11 (64-bit)</li>
                <li style={{ marginBottom: '6px' }}>• Per-user installation (no admin UAC required)</li>
                <li style={{ marginBottom: '6px' }}>• Local DPAPI encrypted API key storage</li>
                <li>• In-app auto-updater included</li>
              </ul>
            </div>

            <div>
              <button
                className="btn btn-primary"
                style={{ width: '100%', padding: '14px 20px' }}
                onClick={handleWindowsDownload}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" />
                </svg>
                Download ZayaSetup.exe
              </button>
              <div className="download-meta">
                <span>Version: {windowsVersion}</span>
                <span>Size: ~48 MB</span>
              </div>
            </div>
          </div>

          {/* Android Card */}
          <div className="download-card">
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <span style={{ fontSize: '24px' }}>📱 Android</span>
                <span style={{ background: 'rgba(0, 255, 136, 0.15)', color: 'var(--accent-green)', padding: '4px 10px', borderRadius: '4px', fontSize: '12px', fontWeight: 700 }}>
                  COMPANION
                </span>
              </div>
              <h2 style={{ fontSize: '22px', color: '#ffffff', marginBottom: '8px' }}>Zaya Companion</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
                Pairs your smartphone to your laptop runtime for mobile conversational voice, cellular call answering, and notification sync.
              </p>

              <ul style={{ listStyle: 'none', marginBottom: '28px', fontSize: '13px', color: 'var(--text-muted)' }}>
                <li style={{ marginBottom: '6px' }}>• Android 8.0+ (API 26+)</li>
                <li style={{ marginBottom: '6px' }}>• Local Wi-Fi / secure tunnel sync</li>
                <li style={{ marginBottom: '6px' }}>• No credentials stored on device</li>
                <li>• Foreground service call alerts</li>
              </ul>
            </div>

            <div>
              <button
                className="btn btn-secondary"
                style={{ width: '100%', marginBottom: '10px', opacity: 0.65, cursor: 'not-allowed' }}
                title="Google Play Store review track pending"
              >
                Google Play — Coming Soon
              </button>
              <button
                className="btn btn-secondary"
                style={{ width: '100%', padding: '10px 16px' }}
                onClick={handleAndroidDownload}
              >
                Download Official APK (v{androidVersion})
              </button>
              <div className="download-meta">
                <span>Version: {androidVersion}</span>
                <span>Size: ~24 MB</span>
              </div>
            </div>
          </div>
        </div>

        {/* Verification Box */}
        <div
          style={{
            maxWidth: '900px',
            margin: '0 auto',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '24px',
          }}
        >
          <h3 style={{ color: '#ffffff', fontSize: '16px', marginBottom: '10px' }}>
            Security & Hash Verification
          </h3>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
            To verify that your downloaded <code>ZayaSetup.exe</code> matches the official distribution byte-for-byte, run in PowerShell:
          </p>
          <div className="code-block" style={{ margin: 0 }}>
            Get-FileHash -Algorithm SHA256 .\ZayaSetup.exe
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '10px' }}>
            Official SHA-256 digests are published in{' '}
            <a href="/releases" onClick={(e) => { e.preventDefault(); navigate('/releases'); }}>
              Releases
            </a>{' '}
            and{' '}
            <a href="https://github.com/sajancodes/zaya-companion-releases/releases/latest/download/SHA256SUMS.txt" target="_blank" rel="noopener">
              SHA256SUMS.txt
            </a>.
          </p>
        </div>
      </div>
    </section>
  );
};
