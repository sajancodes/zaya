import React from 'react';

export const Security: React.FC = () => {
  return (
    <section className="section" style={{ paddingTop: '50px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div className="section-header">
          <div className="hero-tag">Integrity</div>
          <h1 className="section-title">Security & Trust Model</h1>
          <p className="section-desc">
            Technical security guarantees, cryptographic protections, and vulnerability reporting guidelines.
          </p>
        </div>

        <div className="card" style={{ padding: '40px', fontSize: '15px', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          <h2 style={{ color: '#ffffff', fontSize: '20px', marginBottom: '12px' }}>1. Official Download Sources</h2>
          <p style={{ marginBottom: '20px' }}>
            Only download Zaya from official verified sources:
          </p>
          <ul style={{ marginBottom: '20px', paddingLeft: '20px' }}>
            <li>Official Website: <code>https://zaya.sajan.codes/download</code></li>
            <li>Official Release Repository: <code>https://github.com/sajancodes/zaya-companion-releases</code></li>
          </ul>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>2. Cryptographic Integrity Verification</h2>
          <p style={{ marginBottom: '12px' }}>
            Every published binary has its SHA-256 digest recorded in the authoritative <code>SHA256SUMS.txt</code> manifest.
            You can verify your installer in PowerShell before running:
          </p>
          <div className="code-block">
            Get-FileHash -Algorithm SHA256 .\ZayaSetup.exe
          </div>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>3. Credential Protection via Windows DPAPI</h2>
          <p style={{ marginBottom: '20px' }}>
            API keys are protected at rest via the Windows Data Protection API (<code>CryptProtectData</code>).
            The encryption key is derived by the Windows kernel from your logon password and security identifier (SID).
            Even if a malicious party copies your <code>api_keys.json</code> to another computer or logs in under another account on the same machine, they cannot decrypt your credentials.
          </p>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>4. Isolated Optical Worker & Ephemeral Video</h2>
          <p style={{ marginBottom: '20px' }}>
            Webcam video frames never enter Zaya's main application thread or LLM context.
            Instead, frames are processed in-memory inside an isolated child worker (<code>ZayaHandWorker.exe</code>),
            analyzed strictly for 21 normalized landmarks, and immediately freed from RAM.
          </p>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>5. Responsible Vulnerability Disclosure</h2>
          <p style={{ marginBottom: '12px' }}>
            If you discover a security vulnerability in Zaya, we appreciate your responsible disclosure.
            Please send details, reproduction steps, and proof-of-concept information to:
          </p>
          <div className="code-block" style={{ margin: '10px 0' }}>
            ab4290025@gmail.com
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Please do not post unpatched vulnerabilities in public issue trackers.
          </p>
        </div>
      </div>
    </section>
  );
};
