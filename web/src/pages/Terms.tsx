import React from 'react';

export const Terms: React.FC = () => {
  return (
    <section className="section" style={{ minHeight: '100vh', paddingTop: '60px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
          <div className="section-label">Terms of Service</div>
          <h1 className="editorial-title" style={{ fontSize: '46px', marginBottom: '16px' }}>
            Terms & Open Source Attribution
          </h1>
          <p style={{ color: 'var(--site-muted)', fontSize: '16px', lineHeight: '1.7' }}>
            Usage licensing, model provider disclaimers, and open-source attributions.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: '48px', fontSize: '15px', lineHeight: '1.8', color: 'var(--site-muted)' }}>
          <h2 style={{ color: 'var(--site-ink)', fontSize: '20px', marginBottom: '12px', fontWeight: 600 }}>
            1. Software License
          </h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya is developed by <strong>Yatra Technologies</strong>. The software is provided under its open-source license. You may use, inspect, modify, and distribute the software subject to the terms of the project license and attribution notices.
          </p>

          <h2 style={{ color: 'var(--site-ink)', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            2. Independent Project
          </h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya is independent software and is not affiliated with, endorsed by, or sponsored by Google, OpenAI, Anthropic, Meta, or WhatsApp. You are responsible for complying with the terms of service and acceptable use policies of any third-party model providers whose API keys you configure within Zaya.
          </p>

          <h2 style={{ color: 'var(--site-ink)', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            3. Disclaimer of Warranty & Liability
          </h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya controls computer actions, files, processes, and browser automation as directed by the user. The software is provided "AS IS", without warranty of any kind, express or implied. The author shall not be held liable for any damages, data loss, or operational downtime resulting from the execution of automated or user-confirmed actions.
          </p>

          <h2 style={{ color: 'var(--site-ink)', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            4. Upstream Open Source Attributions
          </h2>
          <p style={{ margin: 0 }}>
            Zaya proudly incorporates open-source technologies including Google MediaPipe, Babylon.js, Playwright, faster-whisper, Piper TTS, WebRTC VAD, and SQLite. All third-party copyrights and intellectual property rights belong to their respective owners.
          </p>
        </div>
      </div>
    </section>
  );
};
