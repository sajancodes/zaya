import React from 'react';

export const Terms: React.FC = () => {
  return (
    <section className="section" style={{ paddingTop: '50px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div className="section-header">
          <div className="hero-tag">Agreement</div>
          <h1 className="section-title">Terms of Service</h1>
          <p className="section-desc">
            Last Updated: October 2026 · Notice: Preliminary terms subject to owner and legal review before public commercial launch.
          </p>
        </div>

        <div className="card" style={{ padding: '40px', fontSize: '15px', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          <h2 style={{ color: '#ffffff', fontSize: '20px', marginBottom: '12px' }}>1. Acceptance of Terms</h2>
          <p style={{ marginBottom: '20px' }}>
            By downloading, installing, or operating Zaya or the Zaya Companion application, you agree to be bound by these Terms of Service.
            Zaya is created and developed by Sajan Rai.
          </p>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>2. Permitted and Prohibited Uses</h2>
          <p style={{ marginBottom: '12px' }}>
            Zaya is designed as an autonomous personal assistant for local desktop productivity, mechanical visualization, voice coordination, and workflow execution.
          </p>
          <ul style={{ marginBottom: '20px', paddingLeft: '20px' }}>
            <li>You agree not to use Zaya to execute malicious software, conduct unauthorized penetration testing against third-party systems, or automate abusive behavior.</li>
            <li>You agree not to circumvent security gates, reverse-engineer proprietary components, or distribute unauthorized cracked binaries claiming to be Zaya.</li>
          </ul>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>3. Third-Party AI Providers & API Keys</h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya connects to third-party artificial intelligence providers (such as Google AI Studio or OpenAI) using your own API credentials.
            You acknowledge that:
          </p>
          <ul style={{ marginBottom: '20px', paddingLeft: '20px' }}>
            <li>You are solely responsible for compliance with the terms and acceptable use policies of your chosen AI provider.</li>
            <li>Any fees, rate limits, or billing incurred via your API keys are solely between you and the respective provider.</li>
            <li>Zaya has no control over provider availability, model changes, or provider-side content filtering.</li>
          </ul>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>4. Intellectual Property</h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya, its branding, architecture, spatial workspace algorithms, and companion software are the intellectual property of Sajan Rai.
            All third-party open-source components and licenses retain their original upstream attributions.
          </p>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>5. Limitation of Liability</h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya is provided on an "as is" and "as available" basis without warranties of any kind.
            In no event shall the developer be liable for any indirect, incidental, or consequential damages resulting from desktop automation, file operations, hardware interactions, or AI-generated output.
          </p>

          <h2 style={{ color: '#ffffff', fontSize: '20px', margin: '28px 0 12px' }}>6. Contact</h2>
          <p>
            For legal inquiries or terms clarification, reach out to <code>ab4290025@gmail.com</code>.
          </p>
        </div>
      </div>
    </section>
  );
};
