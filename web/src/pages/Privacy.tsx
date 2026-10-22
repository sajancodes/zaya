import React from 'react';

export const Privacy: React.FC = () => {
  return (
    <section className="section" style={{ minHeight: '100vh', paddingTop: '60px' }}>
      <div className="container" style={{ maxWidth: '860px' }}>
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
          <div className="section-label">Privacy Policy</div>
          <h1 className="editorial-title" style={{ fontSize: '46px', marginBottom: '16px' }}>
            Data Privacy & Local Sovereignty
          </h1>
          <p style={{ color: '#8392A6', fontSize: '16px', lineHeight: '1.7' }}>
            Exact disclosures regarding data storage, model transmission, and local network operations.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: '48px', fontSize: '15px', lineHeight: '1.8', color: '#8392A6' }}>
          <h2 style={{ color: '#F4FAFF', fontSize: '20px', marginBottom: '12px', fontWeight: 600 }}>
            1. The Sovereign Local Principle
          </h2>
          <p style={{ marginBottom: '20px' }}>
            Zaya is architected as sovereign desktop software. We do not maintain user databases, central account profiles, or cloud history repositories. Your conversations, memory embeddings, tasks, and configuration files live on your computer in <code>%LOCALAPPDATA%\\Zaya</code>.
          </p>

          <h2 style={{ color: '#F4FAFF', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            2. Continuous Perception Privacy
          </h2>
          <p style={{ marginBottom: '20px' }}>
            Continuous screen perception runs entirely on-device via differential frame hashing (<code>mss</code> and OpenCV) and Windows native WinRT OCR streaming through standard memory buffers. <strong>No video feed of your desktop is ever streamed to cloud servers</strong>.
          </p>

          <h2 style={{ color: '#F4FAFF', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            3. AI Provider Network Transmission
          </h2>
          <p style={{ marginBottom: '20px' }}>
            When you initiate a conversational voice turn or issue a desktop command:
          </p>
          <ul style={{ paddingLeft: '20px', marginBottom: '20px' }}>
            <li><strong>Cloud Provider (e.g. Gemini / OpenAI)</strong>: The active audio packet or text prompt is transmitted directly from your PC to the provider's API. No third-party proxy intercepts your traffic.</li>
            <li><strong>Modular Local Pipeline (Ollama / llama.cpp)</strong>: Speech transcription, language modeling, and voice synthesis run completely offline on your local GPU/CPU. Zero bytes leave your machine.</li>
          </ul>

          <h2 style={{ color: '#F4FAFF', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            4. Optical Tracking & Camera Frames
          </h2>
          <p style={{ marginBottom: '20px' }}>
            Your webcam is only accessed if you explicitly enable optical hand tracking. The camera remains completely <strong>OFF</strong> at normal startup. When active, frames are analyzed inside an isolated child worker strictly for 21 joint landmark coordinates; image frames are immediately discarded from memory without writing to disk.
          </p>

          <h2 style={{ color: '#F4FAFF', fontSize: '20px', margin: '32px 0 12px', fontWeight: 600 }}>
            5. WhatsApp & Android Companion Communication
          </h2>
          <p style={{ margin: 0 }}>
            WhatsApp auto-replies use only current session activity (e.g. listening to music or working on a project) and will never expose private conversation logs or files. The Android companion connects to your laptop over your local home Wi-Fi using encrypted WebSockets; keys are protected by the Android Hardware Keystore.
          </p>
        </div>
      </div>
    </section>
  );
};
