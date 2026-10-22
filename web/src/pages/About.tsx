import React from 'react';

export const About: React.FC = () => {
  return (
    <section className="section" style={{ paddingTop: '50px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div className="section-header">
          <div className="hero-tag">Creator</div>
          <h1 className="section-title">About Zaya & Sajan Rai</h1>
          <p className="section-desc">
            The story, architectural principles, and craftsmanship behind the spatial assistant.
          </p>
        </div>

        <div className="card" style={{ padding: '40px', fontSize: '15px', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          <h2 style={{ color: '#ffffff', fontSize: '20px', marginBottom: '12px' }}>Created and Developed by Sajan Rai</h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya began with a clear dissatisfaction with conventional AI assistants.
            Most contemporary AI tools are trapped inside browser tabs or mobile bubbles, unable to see your screen, touch your software, or understand physical mid-air gestures.
          </p>
          <p style={{ marginBottom: '20px' }}>
            Sajan Rai created Zaya to bridge the gap between artificial intelligence and genuine desktop autonomy.
            By fusing real-time streaming audio with continuous perception, 3D spatial mechanical visualization, and optical hand gesture tracking, Zaya transforms your computer from a passive screen into an interactive spatial environment.
          </p>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>Core Principles</h2>
          <ul style={{ marginBottom: '24px', paddingLeft: '20px' }}>
            <li style={{ marginBottom: '10px' }}>
              <b>1. Sovereign & Local First</b>: Your personal data, memories, and workspace belong to you. Computation is run on your machine wherever possible, and sensitive keys are guarded by Windows DPAPI.
            </li>
            <li style={{ marginBottom: '10px' }}>
              <b>2. No Illusory Promises</b>: Zaya does not pretend to be omniscient or claim features that do not exist. Features are engineered rigorously with strict physical verification.
            </li>
            <li style={{ marginBottom: '10px' }}>
              <b>3. Explicit Human Confirmation</b>: Dangerous operations, irreversible file deletions, or external automated actions always yield to the owner's confirmation gate.
            </li>
          </ul>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>Connect with the Creator</h2>
          <p style={{ marginBottom: '10px' }}>
            Follow development progress, explore source repositories, or get in touch:
          </p>
          <ul style={{ listStyle: 'none', color: 'var(--accent-cyan)' }}>
            <li style={{ marginBottom: '8px' }}>
              • GitHub: <a href="https://github.com/sajancodes" target="_blank" rel="noopener">github.com/sajancodes</a>
            </li>
            <li style={{ marginBottom: '8px' }}>
              • Releases: <a href="https://github.com/sajancodes/zaya-companion-releases" target="_blank" rel="noopener">github.com/sajancodes/zaya-companion-releases</a>
            </li>
            <li>
              • Email: <a href="mailto:ab4290025@gmail.com">ab4290025@gmail.com</a>
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
};
