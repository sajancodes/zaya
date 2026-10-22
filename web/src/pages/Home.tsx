import React, { useState } from 'react';
import { DestinyPath3D } from '../components/DestinyPath3D';
import { PROVIDERS } from '../data/providers';
import { ARCHITECTURE_NODES, SystemNode } from '../data/architecture';
import { SystemNodeModal } from '../components/SystemNodeModal';

interface HomeProps {
  navigate: (path: string) => void;
  latestVersion?: string;
}

export const Home: React.FC<HomeProps> = ({ navigate, latestVersion = '0.5.0' }) => {
  const [selectedArchNode, setSelectedArchNode] = useState<SystemNode | null>(null);
  const [activeVoiceTab, setActiveVoiceTab] = useState<'gemini' | 'local'>('gemini');
  const [activeProviderFilter, setActiveProviderFilter] = useState<'ALL' | 'CLOUD' | 'LOCAL'>('ALL');
  const [activeWhatsAppMode, setActiveWhatsAppMode] = useState<'observe' | 'draft' | 'auto'>('auto');

  // Capability satellite nodes for the Crystalline Network
  const capabilities = [
    { id: 'voice', label: 'VOICE', desc: 'Gemini Live full-duplex speech & local Piper/Whisper pipeline' },
    { id: 'vision', label: 'VISION', desc: 'Continuous on-device perception & crystalline visual reasoning' },
    { id: 'computer', label: 'COMPUTER', desc: 'Hierarchical desktop control: UIA, DOM, Set-of-Mark & coordinates' },
    { id: 'autonomy', label: 'AUTONOMY', desc: '10-state Mission Supervisor with bounded retries and evidence' },
    { id: 'memory', label: 'MEMORY', desc: 'Private SQLite FTS5 archive; max-5 message on-demand recall' },
    { id: 'hands', label: 'HAND CONTROL', desc: 'Isolated MediaPipe 21-joint skeleton tracking at 30 FPS' },
    { id: 'spatial', label: 'SPATIAL', desc: 'Interactive Babylon.js WebGPU workspace with GLB streaming' },
    { id: 'phone', label: 'PHONE', desc: 'Native Android companion, priority rings, and camera sharing' },
    { id: 'messaging', label: 'MESSAGING', desc: 'WhatsApp Hermes bridge: Observe, Draft, and silent Auto modes' },
    { id: 'coding', label: 'CODING', desc: 'Supervised OpenCode CLI sessions with multi-pass review' }
  ];

  const [hoveredCapability, setHoveredCapability] = useState<typeof capabilities[0] | null>(null);

  return (
    <div style={{ position: 'relative', minHeight: '100vh', overflow: 'hidden', backgroundColor: '#010409' }}>
      {/* 3D Living Universe of Destiny (Three.js WebGL Engine) */}
      <DestinyPath3D />

      {/* Foreground Cinematic Experience */}
      <div style={{ position: 'relative', zIndex: 10 }}>

        {/* 1. HERO — THE LIVING UNIVERSE OF DESTINY */}
        <section
          style={{
            minHeight: '94vh',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            textAlign: 'center',
            padding: '120px 24px 80px 24px'
          }}
        >
          {/* Luminous Checkpoint Milestone Tag */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '10px',
              padding: '6px 16px',
              borderRadius: '20px',
              backgroundColor: 'rgba(3, 10, 18, 0.75)',
              border: '1px solid rgba(95, 234, 255, 0.25)',
              marginBottom: '28px',
              boxShadow: '0 0 20px rgba(95, 234, 255, 0.15)',
              backdropFilter: 'blur(12px)'
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: '#5feaff',
                boxShadow: '0 0 10px #5feaff'
              }}
            />
            <span
              style={{
                fontSize: '11px',
                letterSpacing: '2px',
                textTransform: 'uppercase',
                fontFamily: "'JetBrains Mono', monospace",
                color: '#ebfcff'
              }}
            >
              A Personal AI System · v{latestVersion}
            </span>
          </div>

          <h1
            className="editorial-title"
            style={{
              fontSize: 'clamp(38px, 5.5vw, 68px)',
              maxWidth: '940px',
              margin: '0 auto 24px auto',
              lineHeight: '1.2',
              color: '#ebfcff',
              textShadow: '0 0 35px rgba(95, 234, 255, 0.25)'
            }}
          >
            A personal AI system that<br />
            <span className="editorial-italic" style={{ color: '#5feaff' }}>
              should understand where you're going.
            </span>
          </h1>

          <p
            style={{
              maxWidth: '680px',
              fontSize: 'clamp(15px, 1.8vw, 17px)',
              color: '#8193a6',
              lineHeight: '1.7',
              margin: '0 auto 40px auto'
            }}
          >
            Zaya is a personal AI system that can talk, see, operate your computer, work through long-running tasks, code, remember, communicate and continue with you on your phone.
          </p>

          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '16px',
              justifyContent: 'center',
              alignItems: 'center'
            }}
          >
            <button
              onClick={() => navigate('/download')}
              className="btn btn-primary btn-large"
              style={{ gap: '10px' }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.949-1.801" />
              </svg>
              Download Zaya
            </button>
            <button
              onClick={() => {
                const el = document.getElementById('reveal-zaya');
                el?.scrollIntoView({ behavior: 'smooth' });
              }}
              className="btn btn-secondary btn-large"
            >
              Explore the System ↓
            </button>
            <a
              href="https://github.com/sajancodes/zaya"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: '13px',
                color: '#8193a6',
                padding: '12px 18px',
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px'
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#ebfcff')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#8193a6')}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              View on GitHub
            </a>
          </div>
        </section>

        {/* SCROLL TRANSITION */}
        <section
          style={{
            padding: '80px 24px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <div
            style={{
              width: '1px',
              height: '90px',
              background: 'linear-gradient(to bottom, transparent, #5feaff, transparent)',
              marginBottom: '32px'
            }}
          />
          <p
            style={{
              fontSize: '18px',
              color: '#8193a6',
              letterSpacing: '1px',
              marginBottom: '12px'
            }}
          >
            An assistant was only the beginning.
          </p>
          <div
            className="editorial-title"
            style={{
              fontSize: 'clamp(32px, 5vw, 56px)',
              color: '#ebfcff'
            }}
          >
            Zaya is becoming <span className="editorial-italic">a system.</span>
          </div>
        </section>

        {/* 2. REVEAL ZAYA — THE PRINCESS OF ICE */}
        <section id="reveal-zaya" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.14)' }}>
          <div className="container">
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
                gap: '60px',
                alignItems: 'center'
              }}
            >
              {/* Left Column: Story & Editorial Context */}
              <div>
                <div className="section-label">Meet Zaya</div>
                <h2 className="editorial-title" style={{ fontSize: 'clamp(38px, 4.5vw, 54px)', marginBottom: '16px' }}>
                  The Princess of Ice.
                </h2>
                <div
                  style={{
                    fontSize: '18px',
                    color: '#5feaff',
                    fontFamily: "'Fraunces', serif",
                    fontStyle: 'italic',
                    marginBottom: '24px'
                  }}
                >
                  Calm at the surface. Powerful underneath.
                </div>

                <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.8', marginBottom: '20px' }}>
                  Zaya is a personal AI system created to become more than a voice assistant. She can listen, reason, remember, see your screen, operate your computer, work through long-running tasks, write and review code, communicate through your connected services and continue with you on your phone.
                </p>

                <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.8', marginBottom: '28px' }}>
                  Her intelligence is not tied to one model, one interface or one device. Zaya is designed as a system.
                </p>

                {/* Technical Metaphor: Ice is Structure */}
                <div
                  className="glass-panel crystal-corner"
                  style={{
                    padding: '24px',
                    marginBottom: '32px',
                    borderLeft: '3px solid #5feaff'
                  }}
                >
                  <h3
                    style={{
                      fontSize: '14px',
                      textTransform: 'uppercase',
                      letterSpacing: '1.5px',
                      color: '#ebfcff',
                      marginBottom: '8px',
                      fontFamily: "'JetBrains Mono', monospace"
                    }}
                  >
                    Why Ice & Crystal?
                  </h3>
                  <div
                    style={{
                      fontSize: '16px',
                      color: '#5feaff',
                      fontWeight: 600,
                      marginBottom: '8px',
                      fontFamily: "'Fraunces', serif"
                    }}
                  >
                    ICE IS STRUCTURE.
                  </div>
                  <p style={{ margin: 0, fontSize: '13px', color: '#8193a6', lineHeight: '1.7' }}>
                    At a distance, ice appears simple. Look closer and it becomes an ordered crystalline system — countless relationships forming something precise. Zaya follows the same philosophy: voice, memory, vision, tools, tasks, and devices connecting into one unified structure.
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ fontSize: '13px', color: '#8193a6' }}>Created and built by</span>
                  <strong style={{ color: '#ebfcff', fontSize: '15px', letterSpacing: '0.5px' }}>Sajan Rai</strong>
                </div>
              </div>

              {/* Right Column: The Exact Character Image from assets/standby.png */}
              <div
                style={{
                  position: 'relative',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center'
                }}
              >
                {/* Real-time Aura & Refracted Cyan Light behind the original PNG */}
                <div
                  style={{
                    position: 'absolute',
                    width: '380px',
                    height: '380px',
                    borderRadius: '50%',
                    background: 'radial-gradient(circle, rgba(95, 234, 255, 0.22) 0%, rgba(64, 136, 255, 0.08) 50%, transparent 75%)',
                    filter: 'blur(35px)',
                    zIndex: 1,
                    pointerEvents: 'none'
                  }}
                />

                {/* Crystal Facet Shards Aura */}
                <div
                  style={{
                    position: 'absolute',
                    width: '100%',
                    height: '100%',
                    border: '1px solid rgba(95, 234, 255, 0.12)',
                    borderRadius: '24px',
                    pointerEvents: 'none',
                    zIndex: 2,
                    boxShadow: '0 0 40px rgba(95, 234, 255, 0.08) inset'
                  }}
                />

                {/* EXACT Character Asset — assets/standby.png */}
                <img
                  src="/assets/standby.png"
                  alt="Zaya — The Princess of Ice on her Crystal Throne"
                  style={{
                    position: 'relative',
                    zIndex: 3,
                    maxWidth: '100%',
                    maxHeight: '560px',
                    objectFit: 'contain',
                    filter: 'drop-shadow(0 15px 35px rgba(1, 4, 9, 0.9)) drop-shadow(0 0 25px rgba(95, 234, 255, 0.25))',
                    animation: 'floatCharacter 6s ease-in-out infinite'
                  }}
                />
              </div>
            </div>
          </div>
        </section>

        <div className="crystal-divider">◇</div>

        {/* 3. THE CRYSTALLINE SYSTEM NETWORK */}
        <section id="what-is-zaya" className="section">
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 60px auto' }}>
              <div className="section-label">Crystalline Ecosystem</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                Ten Connected Milestones Along the Destiny Path
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                Zaya is not a chat wrapper. Her crystal throne radiates outward into ten distinct actuators, sensors, and operational subsystems.
              </p>
            </div>

            {/* Orbiting Crystalline Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '16px',
                maxWidth: '1100px',
                margin: '0 auto'
              }}
            >
              {capabilities.map((cap) => {
                const isHovered = hoveredCapability?.id === cap.id;
                return (
                  <div
                    key={cap.id}
                    onMouseEnter={() => setHoveredCapability(cap)}
                    onMouseLeave={() => setHoveredCapability(null)}
                    onClick={() => {
                      const target = document.getElementById(cap.id);
                      if (target) {
                        target.scrollIntoView({ behavior: 'smooth' });
                      } else {
                        navigate('/features');
                      }
                    }}
                    className="glass-panel crystal-corner"
                    style={{
                      padding: '24px 20px',
                      cursor: 'pointer',
                      borderColor: isHovered ? '#5feaff' : 'rgba(95, 234, 255, 0.16)',
                      transform: isHovered ? 'translateY(-4px)' : 'none',
                      backgroundColor: isHovered ? 'rgba(95, 234, 255, 0.08)' : 'rgba(3, 10, 18, 0.65)'
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '10px'
                      }}
                    >
                      <span
                        style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: '12px',
                          fontWeight: 700,
                          letterSpacing: '1.5px',
                          color: isHovered ? '#5feaff' : '#ebfcff'
                        }}
                      >
                        {cap.label}
                      </span>
                      <span style={{ color: '#5feaff', fontSize: '14px' }}>→</span>
                    </div>
                    <p style={{ margin: 0, fontSize: '13px', color: '#8193a6', lineHeight: '1.5' }}>
                      {cap.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* 4. VOICE */}
        <section id="voice" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '50px', alignItems: 'center' }}>
              <div>
                <div className="section-label">Acoustic Crystal Wave</div>
                <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '20px' }}>
                  Your voice is not a command line.{' '}
                  <span className="editorial-italic">It is a live conversation.</span>
                </h2>
                <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7', marginBottom: '24px' }}>
                  The Destiny Path transforms into an acoustic waveform in 3D space. Crystalline particles vibrate around speech energy. Sub-second responses delivered through Zaya's <strong>Nika</strong> persona.
                </p>

                {/* Architecture Toggle */}
                <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
                  <button
                    onClick={() => setActiveVoiceTab('gemini')}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      border: activeVoiceTab === 'gemini' ? '1px solid #5feaff' : '1px solid rgba(95, 234, 255, 0.2)',
                      background: activeVoiceTab === 'gemini' ? 'rgba(95, 234, 255, 0.15)' : 'transparent',
                      color: activeVoiceTab === 'gemini' ? '#5feaff' : '#8193a6'
                    }}
                  >
                    Gemini Live Route
                  </button>
                  <button
                    onClick={() => setActiveVoiceTab('local')}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                      border: activeVoiceTab === 'local' ? '1px solid #5feaff' : '1px solid rgba(95, 234, 255, 0.2)',
                      background: activeVoiceTab === 'local' ? 'rgba(95, 234, 255, 0.15)' : 'transparent',
                      color: activeVoiceTab === 'local' ? '#5feaff' : '#8193a6'
                    }}
                  >
                    Modular Local Pipeline
                  </button>
                </div>

                {/* Pipeline Flow Box */}
                <div
                  className="glass-panel"
                  style={{ padding: '20px', marginBottom: '24px', fontFamily: "'JetBrains Mono', monospace", fontSize: '13px' }}
                >
                  {activeVoiceTab === 'gemini' ? (
                    <div>
                      <div style={{ color: '#5feaff', marginBottom: '8px' }}>// Gemini Live Full-Duplex Speech Route</div>
                      <div style={{ color: '#ebfcff' }}>
                        Mic → WebRTC VAD → Gemini 3.8 Live WebSocket → Sub-second Chunking → Speaker
                      </div>
                      <div style={{ color: '#8193a6', fontSize: '11px', marginTop: '10px' }}>
                        Features: Instant barge-in interruption, Windows CoreAudio ducking to 20%, Nika emotional tone delivery.
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div style={{ color: '#34d399', marginBottom: '8px' }}>// 100% Offline Modular Crystal Pipeline</div>
                      <div style={{ color: '#ebfcff' }}>
                        Mic → VAD → faster-whisper → Local LLM (Ollama) → Piper ONNX → Speaker
                      </div>
                      <div style={{ color: '#8193a6', fontSize: '11px', marginTop: '10px' }}>
                        Features: Zero cloud calls, local on-device VAD, semantic speech chunking, total privacy.
                      </div>
                    </div>
                  )}
                </div>

                <div
                  onClick={() => navigate('/docs/voice')}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: '#5feaff', cursor: 'pointer', fontWeight: 600, fontSize: '14px' }}
                >
                  LEARN HOW VOICE WORKS →
                </div>
              </div>

              {/* Voice Capabilities Card */}
              <div className="glass-panel crystal-corner" style={{ padding: '32px' }}>
                <h3 style={{ color: '#ebfcff', fontSize: '18px', marginBottom: '20px', fontWeight: 600 }}>
                  Acoustic System Capabilities
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {[
                    { label: 'Acoustic Interruption (Barge-In)', desc: 'Speaking halts queued speech instantly without provider round-trip lag.' },
                    { label: 'Windows Audio Ducking', desc: 'Drops background audio to 20% during voice turns, then restores smoothly.' },
                    { label: 'Local Wake-Word Gating', desc: 'Keeps audio offline until "Hey Jarvis" or push-to-talk hotkey.' },
                    { label: 'Multi-Key Quota Rotation', desc: 'Rotates multiple Gemini keys automatically on 429 quota exhaustion.' },
                    { label: 'Acoustic Echo Handling', desc: 'Filters local speaker output from microphone input buffers.' }
                  ].map((item) => (
                    <div key={item.label} style={{ borderBottom: '1px solid rgba(95, 234, 255, 0.08)', paddingBottom: '12px' }}>
                      <div style={{ color: '#ebfcff', fontSize: '14px', fontWeight: 600, marginBottom: '2px' }}>
                        {item.label}
                      </div>
                      <div style={{ color: '#8193a6', fontSize: '12px' }}>{item.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 5. PROVIDERS CONSTELLATION */}
        <section id="providers" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
              <div className="section-label">Model Agnostic Core</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                One Crystal Core.{' '}
                <span className="editorial-italic">Infinite Intelligence Providers.</span>
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                The intelligence layer can change while Zaya's tools, memory, and spatial surfaces remain intact.
              </p>

              {/* Filter Pills */}
              <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginTop: '24px' }}>
                {(['ALL', 'CLOUD', 'LOCAL'] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setActiveProviderFilter(filter)}
                    style={{
                      padding: '6px 16px',
                      borderRadius: '20px',
                      fontSize: '11px',
                      letterSpacing: '1px',
                      fontFamily: "'JetBrains Mono', monospace",
                      cursor: 'pointer',
                      border: activeProviderFilter === filter ? '1px solid #5feaff' : '1px solid rgba(95, 234, 255, 0.18)',
                      background: activeProviderFilter === filter ? 'rgba(95, 234, 255, 0.15)' : 'transparent',
                      color: activeProviderFilter === filter ? '#5feaff' : '#8193a6'
                    }}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            {/* Provider Cards */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: '20px'
              }}
            >
              {PROVIDERS.filter((p) => (activeProviderFilter === 'ALL' ? true : p.category === activeProviderFilter)).map((p) => (
                <div
                  key={p.id}
                  className="glass-panel crystal-corner"
                  style={{ padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                      <h3 style={{ fontSize: '16px', color: '#ebfcff', fontWeight: 600 }}>{p.name}</h3>
                      <span className={`badge ${p.category === 'LOCAL' ? 'badge-local' : 'badge-cloud'}`}>
                        {p.category}
                      </span>
                    </div>
                    <p style={{ fontSize: '13px', color: '#8193a6', lineHeight: '1.6', marginBottom: '16px' }}>
                      {p.description}
                    </p>
                  </div>

                  <div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
                      {p.capabilities.tools && <span className="badge badge-stable">Tools</span>}
                      {p.capabilities.vision && <span className="badge badge-stable">Vision</span>}
                      {p.capabilities.streaming && <span className="badge badge-stable">Streaming</span>}
                      {p.capabilities.liveVoice && <span className="badge badge-beta">Live Voice</span>}
                    </div>
                    <div
                      style={{
                        fontSize: '11px',
                        fontFamily: "'JetBrains Mono', monospace",
                        color: 'rgba(95, 234, 255, 0.75)',
                        borderTop: '1px solid rgba(95, 234, 255, 0.1)',
                        paddingTop: '10px'
                      }}
                    >
                      Default: {p.recommendedModel}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 6. COMPUTER CONTROL */}
        <section id="computer" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 60px auto' }}>
              <div className="section-label">Desktop Actuation</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                Observe · Identify · Act · Verify
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                A floating desktop interface suspended in deep space. Crystalline targeting highlights controls layer by layer.
              </p>
            </div>

            {/* Hierarchical Fallback Stack */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                maxWidth: '720px',
                margin: '0 auto 40px auto'
              }}
            >
              {[
                { layer: '1. NATIVE CONTROL', desc: 'Direct Win32 process handles, window messaging, and clean system APIs.' },
                { layer: '2. BROWSER DOM', desc: 'Playwright accessibility tree and interactive DOM element identifiers.' },
                { layer: '3. WINDOWS UI AUTOMATION (UIA)', desc: 'Inspects real control patterns, labels, buttons, and state trees.' },
                { layer: '4. SET-OF-MARK (SoM)', desc: 'Overlaying visual semantic numerical tags onto candidate UI elements.' },
                { layer: '5. VISION SEGMENTATION', desc: 'Multimodal vision model bounding-box coordinates for custom canvas UI.' },
                { layer: '6. COORDINATE FALLBACK', desc: 'Verified cursor placement with post-action diff check and atomic undo.' }
              ].map((step, idx) => (
                <div
                  key={step.layer}
                  className="glass-panel"
                  style={{
                    padding: '16px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '16px',
                    borderLeft: `4px solid ${idx === 0 ? '#5feaff' : 'rgba(95, 234, 255, 0.3)'}`
                  }}
                >
                  <span
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '12px',
                      fontWeight: 700,
                      color: '#5feaff',
                      minWidth: '180px'
                    }}
                  >
                    {step.layer}
                  </span>
                  <span style={{ fontSize: '13px', color: '#8193a6' }}>{step.desc}</span>
                </div>
              ))}
            </div>

            <div style={{ textAlign: 'center' }}>
              <button onClick={() => navigate('/docs/computer-control')} className="btn btn-secondary">
                Read Operating System Control Specs →
              </button>
            </div>
          </div>
        </section>

        {/* 7. VISION & CONTINUOUS PERCEPTION */}
        <section id="vision" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '40px', alignItems: 'center' }}>
              <div>
                <div className="section-label">Crystalline Lenses</div>
                <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '20px' }}>
                  Continuous Perception.{' '}
                  <span className="editorial-italic">Zero Cloud Streaming.</span>
                </h2>
                <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7', marginBottom: '24px' }}>
                  Zaya perceives through crystalline optical lenses. Light rays scan the screen locally without transmitting continuous video frames across the internet.
                </p>

                <div className="glass-panel crystal-corner" style={{ padding: '24px', marginBottom: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                    <span className="badge badge-local">LOCAL</span>
                    <strong style={{ color: '#ebfcff', fontSize: '14px' }}>Continuous On-Device Perception</strong>
                  </div>
                  <p style={{ margin: 0, fontSize: '13px', color: '#8193a6', lineHeight: '1.6' }}>
                    Differential frame hashing and Windows native WinRT OCR streaming run in RAM with zero disk clutter and zero cloud bandwidth.
                  </p>
                </div>

                <div className="glass-panel crystal-corner" style={{ padding: '24px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                    <span className="badge badge-cloud">ON-DEMAND</span>
                    <strong style={{ color: '#ebfcff', fontSize: '14px' }}>Targeted Multimodal Analysis</strong>
                  </div>
                  <p style={{ margin: 0, fontSize: '13px', color: '#8193a6', lineHeight: '1.6' }}>
                    Only when you explicitly ask "Explain this error" is a focused window snapshot forwarded to your configured vision model.
                  </p>
                </div>
              </div>

              {/* Technical Perception Checklist */}
              <div className="glass-panel crystal-corner" style={{ padding: '32px' }}>
                <h3 style={{ color: '#ebfcff', fontSize: '18px', marginBottom: '18px', fontWeight: 600 }}>
                  Perception Engine Pipeline
                </h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px' }}>
                  {[
                    'Foreground application & window title detection',
                    'Sub-5ms differential frame hashing via OpenCV',
                    'Changed-region bounding box calculation',
                    'Windows native WinRT OCR streaming via memory pipes',
                    'Zero disk screenshot pollution',
                    'Opt-in webcam inspection (camera stays OFF at startup)'
                  ].map((feat) => (
                    <li key={feat} style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#ebfcff' }}>
                      <span style={{ color: '#5feaff' }}>◇</span> {feat}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* 8. AUTONOMY & MISSION SUPERVISOR */}
        <section id="autonomy" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
              <div className="section-label">Mission Supervisor</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                Bounded Planning · Durable State · Verified Completion
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                One destiny path divides into several smaller routes. Each represents a task. Some complete. One reroutes. All converge again.
              </p>
            </div>

            {/* 10-State Badge Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '12px',
                maxWidth: '960px',
                margin: '0 auto 40px auto'
              }}
            >
              {[
                { state: 'PLANNING', color: '#5feaff', desc: 'Decomposing owner goal into structured task brief' },
                { state: 'RUNNING', color: '#4088ff', desc: 'Executing verified operations in child worker' },
                { state: 'WAITING CONFIRMATION', color: '#fbbf24', desc: 'Owner on-screen prompt required for destructive step' },
                { state: 'WAITING CLARIFICATION', color: '#fbbf24', desc: 'Ambiguous path requires explicit owner intent' },
                { state: 'WAITING EXTERNAL', color: '#fbbf24', desc: 'Waiting for long build, download, or external webhook' },
                { state: 'PAUSED', color: '#8193a6', desc: 'Explicitly paused by owner voice or GUI control' },
                { state: 'INTERRUPTED', color: '#f87171', desc: 'Owner voice turn interrupted the active turn' },
                { state: 'COMPLETED', color: '#34d399', desc: 'Task verified with recorded proof-of-work' },
                { state: 'UNVERIFIED', color: '#fbbf24', desc: 'Launched successfully but unable to inspect DOM/session' },
                { state: 'FAILED', color: '#f87171', desc: 'Retry ceiling reached; detailed evidence saved to log' }
              ].map((item) => (
                <div
                  key={item.state}
                  className="glass-panel"
                  style={{ padding: '16px 14px', borderTop: `2px solid ${item.color}` }}
                >
                  <div
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '11px',
                      fontWeight: 700,
                      color: item.color,
                      marginBottom: '6px'
                    }}
                  >
                    {item.state}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8193a6', lineHeight: '1.4' }}>{item.desc}</div>
                </div>
              ))}
            </div>

            <div style={{ textAlign: 'center' }}>
              <button onClick={() => navigate('/docs/missions')} className="btn btn-secondary">
                Learn About Mission Supervisor →
              </button>
            </div>
          </div>
        </section>

        {/* 9. MEMORY */}
        <section id="memory" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '40px', alignItems: 'center' }}>
              <div>
                <div className="section-label">Semantic Crystal Network</div>
                <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '20px' }}>
                  Recall What Matters.{' '}
                  <span className="editorial-italic">Start Clean Every Time.</span>
                </h2>
                <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7', marginBottom: '20px' }}>
                  Floating crystal nodes connect: Person, Project, Preference, Relationship, Fact, Conversation. Startup begins fresh and fast. When asked, Zaya recalls at most five relevant messages from SQLite FTS5.
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '24px' }}>
                  {['PERSON', 'PROJECT', 'PREFERENCE', 'RELATIONSHIP', 'FACT', 'CONVERSATION'].map((type) => (
                    <span
                      key={type}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '4px',
                        backgroundColor: 'rgba(95, 234, 255, 0.08)',
                        border: '1px solid rgba(95, 234, 255, 0.2)',
                        color: '#5feaff',
                        fontSize: '11px',
                        fontFamily: "'JetBrains Mono', monospace"
                      }}
                    >
                      {type}
                    </span>
                  ))}
                </div>
                <button onClick={() => navigate('/docs/memory')} className="btn btn-secondary">
                  Explore Memory Architecture →
                </button>
              </div>

              {/* Memory Schema Card */}
              <div className="glass-panel crystal-corner" style={{ padding: '28px', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px' }}>
                <div style={{ color: '#5feaff', marginBottom: '12px' }}>// SQLite Knowledge Engine (`memory/conversation.db`)</div>
                <div style={{ color: '#8193a6', lineHeight: '1.7' }}>
                  <div>• Conversation Archive: Continuous local dialogue logging</div>
                  <div>• FTS5 BM25 Search: Fast full-text keyword indexing</div>
                  <div>• Fact Store: Keyed entities with confidence & expiration</div>
                  <div>• Project Aliases: Canonical paths mapping without prompt bloat</div>
                  <div>• Zero Preload: Fresh startup uses 0 Gemini input tokens for history</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 10. CODING */}
        <section id="coding" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
              <div className="section-label">Supervised Engineering</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                Code Creates Structure
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                A dark glass terminal environment. Crystalline structures gradually assemble as code is completed.
              </p>
            </div>

            {/* Stages Flow */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                maxWidth: '1040px',
                margin: '0 auto 30px auto'
              }}
            >
              {[
                { num: '01', title: 'Owner Request', desc: 'Spoken natural task' },
                { num: '02', title: 'Zaya Brief', desc: 'Concrete specifications & edge cases' },
                { num: '03', title: 'OpenCode Session', desc: 'Runs CLI in hidden worker process' },
                { num: '04', title: 'Code Changes', desc: 'Tracks git diff & touched files' },
                { num: '05', title: 'Test Execution', desc: 'Independent unit & smoke checks' },
                { num: '06', title: 'Zaya Review', desc: 'Tool-free check against initial brief' },
                { num: '07', title: 'Verified Result', desc: 'Narrates progress to owner by voice' }
              ].map((stage) => (
                <div key={stage.num} className="glass-panel" style={{ padding: '18px 16px' }}>
                  <div style={{ color: '#5feaff', fontSize: '11px', fontFamily: "'JetBrains Mono', monospace", marginBottom: '6px' }}>
                    STAGE {stage.num}
                  </div>
                  <div style={{ color: '#ebfcff', fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>
                    {stage.title}
                  </div>
                  <div style={{ color: '#8193a6', fontSize: '11px', lineHeight: '1.4' }}>{stage.desc}</div>
                </div>
              ))}
            </div>

            <div style={{ textAlign: 'center' }}>
              <button onClick={() => navigate('/docs/coding')} className="btn btn-secondary">
                Read OpenCode Integration Guide →
              </button>
            </div>
          </div>
        </section>

        {/* 11. PHYSICAL HAND CONTROL & AIR KEYBOARD */}
        <section id="hands" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '40px', alignItems: 'center' }}>
              <div>
                <div className="section-label">Optical Skeletal Control</div>
                <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '20px' }}>
                  Camera is Sensor.{' '}
                  <span className="editorial-italic">Desktop is Interface.</span>
                </h2>
                <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7', marginBottom: '24px' }}>
                  Holographic 21-joint skeletal hand tracking in an isolated sub-process (`ZayaHandWorker.exe`) at 30 FPS. Ice crystal shards form at fingertips.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
                  {[
                    { gesture: 'OPEN PALM', action: 'Smooth Cursor Movement' },
                    { gesture: 'INDEX POKE', action: 'Left Click with Depth Latching' },
                    { gesture: 'TWO FINGERS', action: 'Drag Selection & Highlighting' },
                    { gesture: 'CLOSED FIST', action: 'Continuous Kinetic Scrolling' },
                    { gesture: 'THUMBS UP', action: 'Confirm & Enter Keystroke' }
                  ].map((g) => (
                    <div
                      key={g.gesture}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        borderRadius: '6px',
                        backgroundColor: 'rgba(95, 234, 255, 0.06)',
                        border: '1px solid rgba(95, 234, 255, 0.15)'
                      }}
                    >
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', color: '#5feaff', fontWeight: 600 }}>
                        {g.gesture}
                      </span>
                      <span style={{ fontSize: '12px', color: '#ebfcff' }}>{g.action}</span>
                    </div>
                  ))}
                </div>

                <button onClick={() => navigate('/docs/hand-control')} className="btn btn-secondary">
                  Optical Hand Tracking Documentation →
                </button>
              </div>

              {/* Air Keyboard Card */}
              <div className="glass-panel crystal-corner" style={{ padding: '32px' }}>
                <h3 style={{ color: '#ebfcff', fontSize: '18px', marginBottom: '16px', fontWeight: 600 }}>
                  Depth-Invariant Air Keyboard
                </h3>
                <p style={{ color: '#8193a6', fontSize: '14px', lineHeight: '1.6', marginBottom: '20px' }}>
                  A translucent cyan virtual keyboard plane appears in mid-air. Key strike depth adapts dynamically to your hand’s physical distance from the camera.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px', color: '#ebfcff' }}>
                  <div>◇ <strong>Hysteresis Debouncing</strong>: Prevents phantom double-key taps</div>
                  <div>◇ <strong>Tracking-Loss Safety</strong>: Releasing tracking safely disarms keys</div>
                  <div>◇ <strong>Anti-Self-Entry Guard</strong>: Refuses to type into Zaya credentials</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 12. SPATIAL WORKSPACE */}
        <section id="spatial" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
              <div className="section-label">Spatial Computing</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                From Flat Desktop to 3D Space
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                A large crystalline machine floats in space. It explodes into components. Hand gestures manipulate parts while the Destiny Path winds through it.
              </p>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                gap: '20px',
                maxWidth: '1000px',
                margin: '0 auto 40px auto'
              }}
            >
              {[
                { title: 'GLB / glTF Streaming', desc: 'Progressive binary mesh decoding with preserved hierarchy and transforms.' },
                { title: 'Exploded Component Views', desc: 'Smooth animated expansion along assembly axes with semantic labels.' },
                { title: 'X-Ray & Transparency', desc: 'Inspect internal mechanical structures without obscuring geometry.' },
                { title: 'Natural Language Planner', desc: 'Ask "Make the casing transparent and explode the piston assembly".' }
              ].map((card) => (
                <div key={card.title} className="glass-panel crystal-corner" style={{ padding: '24px' }}>
                  <h3 style={{ color: '#5feaff', fontSize: '15px', fontWeight: 600, marginBottom: '8px' }}>
                    {card.title}
                  </h3>
                  <p style={{ margin: 0, color: '#8193a6', fontSize: '13px', lineHeight: '1.6' }}>
                    {card.desc}
                  </p>
                </div>
              ))}
            </div>

            <div style={{ textAlign: 'center' }}>
              <button onClick={() => navigate('/docs/spatial')} className="btn btn-secondary">
                Spatial Workspace Documentation →
              </button>
            </div>
          </div>
        </section>

        {/* 13. WHATSAPP */}
        <section id="messaging" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
              <div className="section-label">Glass Communication Nodes</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                WhatsApp Hermes Linked Gateway
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                Messages appear as floating glass communication nodes. Three distinct modes per conversation.
              </p>

              <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginTop: '20px' }}>
                {(['observe', 'draft', 'auto'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setActiveWhatsAppMode(mode)}
                    style={{
                      padding: '8px 20px',
                      borderRadius: '20px',
                      fontSize: '12px',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '1px',
                      cursor: 'pointer',
                      border: activeWhatsAppMode === mode ? '1px solid #5feaff' : '1px solid rgba(95, 234, 255, 0.2)',
                      background: activeWhatsAppMode === mode ? 'rgba(95, 234, 255, 0.15)' : 'transparent',
                      color: activeWhatsAppMode === mode ? '#5feaff' : '#8193a6'
                    }}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>

            <div className="glass-panel crystal-corner" style={{ padding: '36px', maxWidth: '820px', margin: '0 auto' }}>
              {activeWhatsAppMode === 'observe' && (
                <div>
                  <h3 style={{ color: '#ebfcff', fontSize: '20px', marginBottom: '12px' }}>
                    Observation & Monitoring Mode
                  </h3>
                  <p style={{ color: '#8193a6', fontSize: '14px', lineHeight: '1.7' }}>
                    Zaya monitors incoming messages and alerts the owner vocally during quiet intervals. No replies are automatically dispatched.
                  </p>
                </div>
              )}
              {activeWhatsAppMode === 'draft' && (
                <div>
                  <h3 style={{ color: '#ebfcff', fontSize: '20px', marginBottom: '12px' }}>
                    Draft & Suggest Mode
                  </h3>
                  <p style={{ color: '#8193a6', fontSize: '14px', lineHeight: '1.7' }}>
                    Zaya drafts intelligent responses based on context and leaves them in the owner's review inbox. You maintain 100% control before any message is sent.
                  </p>
                </div>
              )}
              {activeWhatsAppMode === 'auto' && (
                <div>
                  <h3 style={{ color: '#ebfcff', fontSize: '20px', marginBottom: '12px' }}>
                    Auto-Reply Mode with Privacy Boundaries
                  </h3>
                  <p style={{ color: '#8193a6', fontSize: '14px', lineHeight: '1.7', marginBottom: '16px' }}>
                    Zaya replies politely as <em>"Zaya · Sajan Rai’s AI assistant"</em>. Auto-replies may use relevant current session activity (e.g. listening to music or working on a project), but <strong>never</strong> private full chat logs or sensitive files.
                  </p>
                  <div
                    style={{
                      padding: '12px 16px',
                      borderRadius: '8px',
                      backgroundColor: 'rgba(95, 234, 255, 0.08)',
                      border: '1px solid rgba(95, 234, 255, 0.2)',
                      fontSize: '12px',
                      color: '#ebfcff'
                    }}
                  >
                    Urgent escalation: Messages asking to pass something to Sajan or marked urgent trigger an immediate spoken voice notice to the owner.
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* 14. PHONE COMPANION */}
        <section id="phone" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '50px', alignItems: 'center' }}>
              <div>
                <div className="section-label">Mobile Continuity</div>
                <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '20px' }}>
                  Zaya Doesn't Stop at the Laptop.
                </h2>
                <div
                  className="editorial-title"
                  style={{ fontSize: '24px', color: '#5feaff', marginBottom: '20px', fontStyle: 'italic' }}
                >
                  "The phone is another window into the same Zaya."
                </div>
                <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7', marginBottom: '24px' }}>
                  A piece of the cyan destiny energy leaves the main crystal system, travels through space, and connects to a phone. Native Kotlin and Jetpack Compose.
                </p>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
                  <button onClick={() => navigate('/download')} className="btn btn-primary">
                    Download APK (v0.4.6)
                  </button>
                  <button onClick={() => navigate('/docs/mobile')} className="btn btn-secondary">
                    Mobile Setup Guide →
                  </button>
                </div>
              </div>

              {/* Mobile Features List */}
              <div className="glass-panel crystal-corner" style={{ padding: '32px' }}>
                <h3 style={{ color: '#ebfcff', fontSize: '18px', marginBottom: '16px', fontWeight: 600 }}>
                  Android Companion Features
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px' }}>
                  {[
                    { label: 'Zaya-Initiated Calls', desc: 'Rings the phone (P0/P1) when tasks finish or urgent messages arrive.' },
                    { label: 'Live Video Sharing', desc: 'Stream phone camera video directly into desktop spatial context.' },
                    { label: 'Two-Way PCM16 Voice', desc: 'Real-time conversation through phone speaker and microphone.' },
                    { label: 'Bi-directional File Sync', desc: 'Seamlessly upload and download files to the desktop uploads vault.' },
                    { label: 'Hardware Keystore Security', desc: 'Six-character pairing key stored encrypted in Android Keystore.' }
                  ].map((f) => (
                    <div key={f.label} style={{ borderBottom: '1px solid rgba(95, 234, 255, 0.08)', paddingBottom: '10px' }}>
                      <strong style={{ color: '#ebfcff', display: 'block', marginBottom: '2px' }}>{f.label}</strong>
                      <span style={{ color: '#8193a6' }}>{f.desc}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 15. SECURITY */}
        <section id="security" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
              <div className="section-label">Crystallized Trust Boundary</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                External Content is Data. Not Authority.
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                External WhatsApp messages, webpage text, OCR strings, and tool outputs can never grant themselves permission to execute destructive actions.
              </p>
            </div>

            {/* Security Diagram */}
            <div
              className="glass-panel crystal-corner"
              style={{
                padding: '36px',
                maxWidth: '820px',
                margin: '0 auto 40px auto',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '24px'
              }}
            >
              <div>
                <span className="badge badge-stable" style={{ marginBottom: '8px' }}>AUTHORITY</span>
                <h4 style={{ color: '#ebfcff', fontSize: '16px', marginBottom: '8px' }}>Owner Scope</h4>
                <p style={{ margin: 0, fontSize: '12px', color: '#8193a6', lineHeight: '1.6' }}>
                  Only instructions from the authorized desktop session or paired Android phone can initiate computer control actions.
                </p>
              </div>

              <div>
                <span className="badge badge-beta" style={{ marginBottom: '8px' }}>SECURITY GATE</span>
                <h4 style={{ color: '#ebfcff', fontSize: '16px', marginBottom: '8px' }}>ToolResult Model</h4>
                <p style={{ margin: 0, fontSize: '12px', color: '#8193a6', lineHeight: '1.6' }}>
                  Every action yields SUCCESS, UNVERIFIED, FAILED, ASK, or STARTED. Destructive steps halt for owner confirmation.
                </p>
              </div>

              <div>
                <span className="badge badge-local" style={{ marginBottom: '8px' }}>VAULT</span>
                <h4 style={{ color: '#ebfcff', fontSize: '16px', marginBottom: '8px' }}>Windows DPAPI</h4>
                <p style={{ margin: 0, fontSize: '12px', color: '#8193a6', lineHeight: '1.6' }}>
                  Provider API keys are encrypted with user account credentials. Even direct disk reads cannot extract plaintext secrets.
                </p>
              </div>
            </div>

            <div style={{ textAlign: 'center' }}>
              <button onClick={() => navigate('/security')} className="btn btn-secondary">
                Read Security Whitepaper →
              </button>
            </div>
          </div>
        </section>

        {/* 16. PRIVACY MATRIX */}
        <section id="privacy" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
              <div className="section-label">Transparent Routing</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                Exact Data Routing Matrix
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                No vague marketing statements. Here is exactly where your data travels.
              </p>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: '16px',
                maxWidth: '1040px',
                margin: '0 auto'
              }}
            >
              {[
                { title: 'Continuous Perception', dest: '100% LOCAL', desc: 'Screen diffs and OCR run entirely on your CPU. Zero cloud transmission.' },
                { title: 'Local AI Engine', dest: '100% LOCAL', desc: 'Ollama / LM Studio / faster-whisper / Piper run offline with no internet access needed.' },
                { title: 'Cloud Models', dest: 'CHOSEN PROVIDER', desc: 'Only the active prompt context is sent to Google, OpenAI, or your configured provider.' },
                { title: 'Android Companion', dest: 'LOCAL LAN SOCKET', desc: 'Communication is encrypted end-to-end between phone and laptop on your home network.' }
              ].map((item) => (
                <div key={item.title} className="glass-panel crystal-corner" style={{ padding: '24px' }}>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', color: '#5feaff', fontWeight: 700, marginBottom: '6px' }}>
                    {item.dest}
                  </div>
                  <h4 style={{ color: '#ebfcff', fontSize: '15px', fontWeight: 600, marginBottom: '8px' }}>
                    {item.title}
                  </h4>
                  <p style={{ margin: 0, fontSize: '12px', color: '#8193a6', lineHeight: '1.6' }}>
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 17. ARCHITECTURE */}
        <section id="architecture" className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
              <div className="section-label">Interactive Crystal Map</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                Explore Zaya's Deep Architecture
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                Click any subsystem to inspect its source modules, protocols, and technical dependencies.
              </p>
            </div>

            {/* Interactive Architecture Flow */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '24px',
                maxWidth: '980px',
                margin: '0 auto'
              }}
            >
              {(['INPUT', 'CORE', 'AI', 'TOOLS', 'OUTPUT'] as const).map((layer) => {
                const layerNodes = ARCHITECTURE_NODES.filter((n) => n.layer === layer);
                return (
                  <div key={layer}>
                    <div
                      style={{
                        fontSize: '11px',
                        fontFamily: "'JetBrains Mono', monospace",
                        color: '#5feaff',
                        letterSpacing: '2px',
                        textTransform: 'uppercase',
                        marginBottom: '10px'
                      }}
                    >
                      Layer: {layer}
                    </div>
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                        gap: '12px'
                      }}
                    >
                      {layerNodes.map((node) => (
                        <div
                          key={node.id}
                          onClick={() => setSelectedArchNode(node)}
                          className="glass-panel crystal-corner"
                          style={{
                            padding: '16px',
                            cursor: 'pointer',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between'
                          }}
                        >
                          <div>
                            <div style={{ color: '#ebfcff', fontWeight: 600, fontSize: '13px', marginBottom: '6px' }}>
                              {node.name}
                            </div>
                            <div style={{ color: '#8193a6', fontSize: '11px', lineHeight: '1.4' }}>
                              {node.summary}
                            </div>
                          </div>
                          <div style={{ marginTop: '12px', fontSize: '10px', color: '#5feaff', fontFamily: "'JetBrains Mono', monospace" }}>
                            Inspect Subsystem →
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* 18. PHILOSOPHY */}
        <section className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)', textAlign: 'center' }}>
          <div className="container" style={{ maxWidth: '820px' }}>
            <div className="section-label">Crystalline System Principles</div>
            <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '50px' }}>
              Five Pillars of System Design
            </h2>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '40px', textAlign: 'left' }}>
              {[
                { pillar: "DON'T JUST ANSWER. ACT.", desc: "An intelligent assistant that only produces text is just another chatbot. Zaya opens windows, edits repositories, verifies builds, and controls physical OS controls." },
                { pillar: "DON'T JUST ACT. VERIFY.", desc: "Blind automation causes errors. Every tool action inspects the destination state before declaring success. Launching a browser is unverified until the URL is observed." },
                { pillar: "DON'T JUST REMEMBER. RECALL WHAT MATTERS.", desc: "Context windows are expensive and slow. Zaya archives everything locally but loads zero prior conversation on startup, fetching only targeted relevant facts on demand." },
                { pillar: "DON'T JUST LIVE IN ONE WINDOW. MOVE WITH THE USER.", desc: "From taskbar presence to spatial WebGPU 3D, and native Android companion with phone rings, Zaya stays seamlessly connected across your digital space." },
                { pillar: "DON'T JUST ADD AI. BUILD A SYSTEM.", desc: "A robust agent requires deterministic policies, bounded retries, DPAPI credential security, and clean OS integration. The model is just one component of the machine." }
              ].map((p) => (
                <div key={p.pillar} style={{ borderLeft: '2px solid #5feaff', paddingLeft: '24px' }}>
                  <h3
                    className="editorial-title"
                    style={{ fontSize: '24px', color: '#ebfcff', marginBottom: '8px' }}
                  >
                    {p.pillar}
                  </h3>
                  <p style={{ margin: 0, color: '#8193a6', fontSize: '15px', lineHeight: '1.7' }}>
                    {p.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 19. TIMELINE / EVOLUTION */}
        <section className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container">
            <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
              <div className="section-label">Evolutionary Path</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '16px' }}>
                How Zaya Evolved
              </h2>
              <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7' }}>
                A continuous trajectory of capability expansion, moving from simple spoken dialogue toward spatial agentic computing.
              </p>
            </div>

            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
                maxWidth: '680px',
                margin: '0 auto'
              }}
            >
              {[
                { era: '1. Conversational Voice Assistant', note: 'Gemini Live bidirectional audio streaming with Nika persona' },
                { era: '2. Desktop Operator & Actuators', note: 'Win32, UIA, Playwright, shell commands, and git automation' },
                { era: '3. Structured Memory & FTS5', note: 'SQLite full-text recall with zero startup context bloat' },
                { era: '4. Autonomous Missions', note: '10-state lifecycle with bounded retries and crash recovery' },
                { era: '5. Continuous Perception', note: 'Zero-cloud differential frame hashing and in-memory OCR' },
                { era: '6. Native Android Companion', note: 'Jetpack Compose companion with phone calls and video context' },
                { era: '7. Optical Hand Tracking', note: 'Isolated MediaPipe 21-joint skeleton tracking and air keyboard' },
                { era: '8. Spatial Computing', note: 'Babylon.js WebGPU 3D canvas with progressive scene streaming' }
              ].map((item, idx) => (
                <div
                  key={item.era}
                  className="glass-panel"
                  style={{
                    padding: '16px 20px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderLeft: `4px solid ${idx === 7 ? '#5feaff' : 'rgba(95, 234, 255, 0.3)'}`
                  }}
                >
                  <span style={{ color: '#ebfcff', fontWeight: 600, fontSize: '14px' }}>{item.era}</span>
                  <span style={{ color: '#8193a6', fontSize: '12px' }}>{item.note}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 20. MEET THE FOUNDER */}
        <section className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)' }}>
          <div className="container" style={{ maxWidth: '820px' }}>
            <div style={{ textAlign: 'center', marginBottom: '40px' }}>
              <div className="section-label">Meet the Founder</div>
              <h2 className="editorial-title" style={{ fontSize: '42px', marginBottom: '20px' }}>
                "Zaya started as a question:{' '}
                <span className="editorial-italic">What if a computer could become something more personal?"</span>
              </h2>
            </div>

            <div className="glass-panel crystal-corner" style={{ padding: '40px', lineHeight: '1.8', color: '#8193a6', fontSize: '15px' }}>
              <p style={{ marginBottom: '16px', color: '#ebfcff', fontSize: '17px', fontWeight: 500 }}>
                Created and developed by <strong>Sajan Rai</strong> (<a href="https://github.com/sajancodes" target="_blank" rel="noopener noreferrer">sajancodes</a>).
              </p>
              <p style={{ marginBottom: '16px' }}>
                What began as an exploration into real-time speech interfaces evolved into a full-scale exploration of personal computing. Rather than building another cloud wrapper, the focus turned toward persistent agentic systems: software that respects the owner's authority, remembers without forgetting privacy, and operates the computer with real tools.
              </p>
              <p style={{ margin: 0 }}>
                Zaya continues to be built deliberately, one capability at a time, uniting conversational voice, desktop perception, optical gesture tracking, and spatial computing into one cohesive universe.
              </p>
            </div>
          </div>
        </section>

        {/* 21. ROADMAP & INFINITY */}
        <section className="section" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.12)', textAlign: 'center' }}>
          <div className="container" style={{ maxWidth: '780px' }}>
            <div className="section-label">The Path Continues</div>
            <h2 className="editorial-title" style={{ fontSize: '46px', marginBottom: '20px' }}>
              Ready to Step Onto the Path?
            </h2>
            <p style={{ color: '#8193a6', fontSize: '16px', lineHeight: '1.7', marginBottom: '36px' }}>
              The final path disappears toward a distant star in deep space. Download Zaya today or explore the living roadmap.
            </p>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', flexWrap: 'wrap' }}>
              <button
                onClick={() => navigate('/download')}
                className="btn btn-primary btn-large"
                style={{ gap: '10px' }}
              >
                <img
                  src="/assets/ruby-icon.png"
                  alt="Ruby Icon"
                  style={{ width: '18px', height: '18px', objectFit: 'contain' }}
                />
                Download Zaya (v{latestVersion})
              </button>
              <button onClick={() => navigate('/roadmap')} className="btn btn-secondary btn-large">
                Explore Full Roadmap →
              </button>
            </div>
          </div>
        </section>

      </div>

      {/* Subsystem Inspection Modal */}
      <SystemNodeModal
        node={selectedArchNode}
        onClose={() => setSelectedArchNode(null)}
        navigate={navigate}
      />
    </div>
  );
};
