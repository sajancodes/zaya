import React from 'react';

export const Security: React.FC = () => {
  return (
    <section className="section" style={{ minHeight: '100vh', paddingTop: '60px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
          <div className="section-label">Trust & Boundaries</div>
          <h1 className="editorial-title" style={{ fontSize: '46px', marginBottom: '16px' }}>
            Security Architecture & Verification
          </h1>
          <p style={{ color: '#8392A6', fontSize: '16px', lineHeight: '1.7' }}>
            Technical guarantees, hardware-backed cryptographic vaults, and privileged execution limits.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: '48px', fontSize: '15px', lineHeight: '1.8', color: '#8392A6' }}>
          <h2 style={{ color: '#F4FAFF', fontSize: '20px', marginBottom: '12px', fontWeight: 600 }}>
            1. The Owner Trust Boundary
          </h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya implements a strict privilege isolation boundary: <strong>External content is strictly DATA, NOT AUTHORITY</strong>. Incoming WhatsApp messages, scraped webpage text, OCR strings from screen perception, and tool stdout streams can never grant themselves permission to execute system commands, access files outside designated workspace roots, or alter security configurations.
          </p>

          <h2 style={{ color: '#F4FAFF', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            2. ToolResult & The Full Access Confirmation Gate
          </h2>
          <p style={{ marginBottom: '16px' }}>
            Every action executed by Zaya passes through the <code>ToolResult</code> audit model:
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px', marginBottom: '20px' }}>
            {[
              { status: 'SUCCESS', desc: 'Verified and completed with recorded proof-of-work' },
              { status: 'UNVERIFIED', desc: 'Process launched but state cannot be inspected' },
              { status: 'ASK', desc: 'Irreversible action requires on-screen owner confirmation' },
              { status: 'FAILED', desc: 'Execution error; captured in local diagnostic log' }
            ].map((s) => (
              <div key={s.status} style={{ padding: '12px', backgroundColor: 'rgba(8, 20, 35, 0.6)', borderRadius: '6px', border: '1px solid rgba(73, 223, 255, 0.15)' }}>
                <span className="badge badge-stable" style={{ marginBottom: '4px' }}>{s.status}</span>
                <p style={{ margin: 0, fontSize: '11px', color: '#8392A6', marginTop: '4px' }}>{s.desc}</p>
              </div>
            ))}
          </div>
          <p style={{ marginBottom: '20px' }}>
            When <strong>Full Access</strong> is toggled OFF (default), all shell commands and file deletions trigger a modal prompt. Enabling Full Access does not bypass Windows User Account Control (UAC).
          </p>

          <h2 style={{ color: '#F4FAFF', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            3. Hardware-Backed DPAPI Secret Vault
          </h2>
          <p style={{ marginBottom: '20px' }}>
            All user credentials, including Gemini API keys, provider tokens, and mobile pairing hashes, are protected on disk using <strong>Windows DPAPI (Data Protection API)</strong>. Keys are encrypted with the active user account's SID and Windows login credentials. Copying <code>api_keys.json</code> to another machine results in unreadable ciphertext.
          </p>

          <h2 style={{ color: '#F4FAFF', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            4. Isolated Subprocess Workers
          </h2>
          <p style={{ marginBottom: '20px' }}>
            Optical hand tracking and screen OCR run inside an isolated subprocess (<code>ZayaHandWorker.exe</code>). Camera frames are processed strictly in RAM to infer 21 coordinate points and are immediately overwritten. Raw video never touches the application main thread or persistent disk.
          </p>

          <h2 style={{ color: '#F4FAFF', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            5. Binary Integrity & SHA-256 Verification
          </h2>
          <p style={{ marginBottom: '12px' }}>
            Verify official releases before running by checking the SHA-256 hash in PowerShell:
          </p>
          <pre style={{ marginBottom: '24px' }}>
            <code>Get-FileHash -Algorithm SHA256 .\ZayaSetup.exe</code>
          </pre>

          <h2 style={{ color: '#F4FAFF', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            6. Vulnerability Disclosure
          </h2>
          <p style={{ margin: 0 }}>
            To report security considerations responsibly, email <a href="mailto:ab4290025@gmail.com">ab4290025@gmail.com</a>. Please do not post unpatched vulnerabilities in public GitHub issues.
          </p>
        </div>
      </div>
    </section>
  );
};
