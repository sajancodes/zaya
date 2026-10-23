import React from 'react';

export const About: React.FC = () => {
  return (
    <section className="section" style={{ minHeight: '100vh', paddingTop: '60px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
          <div className="section-label">Meet the Founder</div>
          <h1 className="editorial-title" style={{ fontSize: '46px', marginBottom: '20px' }}>
            "Zaya started as a question:{' '}
            <span className="editorial-italic">What if a computer could become something more personal?"</span>
          </h1>
          <p style={{ color: 'var(--site-muted)', fontSize: '16px', lineHeight: '1.7' }}>
            Created and developed by <strong>Sajan Rai</strong> — <a href="https://github.com/sajancodes" target="_blank" rel="noopener noreferrer">sajancodes</a>.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: '48px', fontSize: '15px', lineHeight: '1.8', color: 'var(--site-muted)' }}>
          <h2 style={{ color: 'var(--site-ink)', fontSize: '22px', marginBottom: '16px', fontWeight: 600 }}>
            The Journey to Agentic Personal Computing
          </h2>
          <p style={{ marginBottom: '20px' }}>
            Most contemporary AI assistants remain isolated inside browser tabs or mobile chat bubbles. They cannot observe your desktop errors, understand the context of your open projects, touch your operating system controls, or continue with you seamlessly onto your phone.
          </p>
          <p style={{ marginBottom: '24px' }}>
            Sajan Rai built Zaya to break past these artificial boundaries. Rather than creating a chatbot wrapper, the goal from day one was to build a cohesive personal computing system: an intelligent assistant with sensory perception, voice fluency, physical hand control, and persistent memory that operates with genuine respect for owner sovereignty.
          </p>

          <h2 style={{ color: 'var(--site-ink)', fontSize: '22px', margin: '36px 0 16px', fontWeight: 600 }}>
            Design & Engineering Principles
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '32px' }}>
            {[
              {
                title: '1. Sovereign & Local First',
                desc: 'Conversation archives are stored locally. Windows credentials use DPAPI. Optional local AI and perception are available; enabling a cloud provider can send the relevant voice, text or images to that provider. See the privacy policy for details.'
              },
              {
                title: '2. Deterministic Action Verification',
                desc: 'Zaya does not make empty autonomous claims. Every action is verified against destination states, bounded by retry ceilings, and recorded with auditable proof-of-work.'
              },
              {
                title: '3. Human Confirmation Barrier',
                desc: 'External data from websites, OCR, or WhatsApp can never grant itself permission to run commands. Irreversible changes yield directly to the owner confirmation gate.'
              }
            ].map((p) => (
              <div key={p.title} style={{ borderLeft: '2px solid var(--site-accent)', paddingLeft: '18px' }}>
                <strong style={{ color: 'var(--site-ink)', display: 'block', marginBottom: '4px' }}>{p.title}</strong>
                <span>{p.desc}</span>
              </div>
            ))}
          </div>

          <h2 style={{ color: 'var(--site-ink)', fontSize: '22px', margin: '36px 0 16px', fontWeight: 600 }}>
            Contact & Source
          </h2>
          <p style={{ marginBottom: '16px' }}>
            Zaya is developed actively on GitHub. All coherent updates pass continuous integration checks before release:
          </p>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '14px' }}>
            <li>
              • Public downloads: <a href="https://github.com/sajancodes/zaya-companion-releases" target="_blank" rel="noopener noreferrer">Official Zaya releases</a>
            </li>
            <li>
              • Signed Releases: <a href="https://github.com/sajancodes/zaya-companion-releases" target="_blank" rel="noopener noreferrer">github.com/sajancodes/zaya-companion-releases</a>
            </li>
            <li>
              • Developer Contact: <a href="mailto:ab4290025@gmail.com">ab4290025@gmail.com</a>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
};
