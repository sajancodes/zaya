import React, { lazy, Suspense } from 'react';
import { windowsBeta } from '../data/useReleases';
import { EnterpriseTeaser } from './Enterprise';
const DestinyPath3D = lazy(() => import('../components/DestinyPath3D').then(m => ({default:m.DestinyPath3D})));

const examples = [
  {number:'01', title:'Think out loud.', prompt:'“Help me work through this idea.”', body:'Talk through a question or a plan with voice conversation. Cloud voice needs your own provider key and an internet connection.', href:'/docs/voice', link:'Explore voice'},
  {number:'02', title:'Get help at your desktop.', prompt:'“Help me understand what’s on my screen.”', body:'Ask for screen context and help with computer tasks. Choose what to share and review actions with Full Access off.', href:'/docs/computer-control', link:'See desktop controls'},
  {number:'03', title:'Make something together.', prompt:'“Use OpenCode to build a simple calculator.”', body:'Add the optional Coding Skill for supervised coding sessions. Work stays in your project, with progress you can follow.', href:'/docs/coding', link:'Meet Coding Skill'},
];

export const Home: React.FC<{navigate:(path:string)=>void; latestVersion?:string}> = () => <div className="home-experience">
  <div className="home-universe" aria-hidden="true">{typeof window !== 'undefined' && <Suspense fallback={null}><DestinyPath3D /></Suspense>}</div>
  <div className="home-content">
    <section className="home-hero wrap">
      <div className="hero-copy">
        <a className="release-pill" href="/releases"><span className="status-dot"/> Windows beta {windowsBeta?.version || '0.5.0'} is here <span aria-hidden="true">↗</span></a>
        <p className="eyebrow">Meet Zaya. Your desktop companion.</p>
        <h1>Talk it through.<br/><em>Get things done.</em></h1>
        <p className="hero-description">A personal AI assistant for your Windows desktop. Talk naturally, get help with what’s on screen, and work on projects together—with you in control.</p>
        <div className="action-row"><a className="btn btn-primary" href="/download">Get the Windows beta <span aria-hidden="true">↗</span></a><a className="text-link" href="#meet-zaya">Take a closer look <span aria-hidden="true">↓</span></a></div>
        <p className="hero-note">Windows 10/11 · Own AI provider key · Early, unsigned beta</p>
      </div>
      <figure className="hero-product">
        <div className="product-caption"><span><img src="/assets/zaya-logo.png" alt=""/> A little company for your desktop</span><span className="small-label">REAL APP</span></div>
        <div className="product-screen"><img src="/assets/install/windows-beta-first-run.png" alt="Actual Zaya desktop app showing the first-run setup and Settings & Controls" width="642" height="631" loading="eager"/></div>
        <figcaption><span className="status-dot"/> Your first hello. Actual Windows beta setup.</figcaption>
      </figure>
    </section>
    <div className="home-principles wrap"><span>Created by <strong>Sajan Rai</strong><span className="home-yatra-credit">Co-powered by Yatra Technologies</span></span><span>Voice, desktop & optional coding</span><span>Provider choices. Your permissions.</span></div>
    <section id="meet-zaya" className="home-section wrap">
      <div className="section-heading"><div><p className="eyebrow">A companion with something to do</p><h2>Start with your everyday.</h2></div><p>Three ways to get to know Zaya. These are example requests—not recorded conversations or guaranteed outcomes.</p></div>
      <div className="usecase-list">{examples.map(item=><article className="usecase" key={item.number}><span className="item-number">{item.number}</span><div><h3>{item.title}</h3><p className="example-prompt">{item.prompt}</p></div><div><p>{item.body}</p><a className="text-link" href={item.href}>{item.link} <span aria-hidden="true">↗</span></a></div></article>)}</div>
    </section>
<section id="reveal-zaya" className="section home-section princess-reveal" style={{ borderTop: '1px solid rgba(95, 234, 255, 0.14)' }}>
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
                  <p className="yatra-credit" style={{marginTop:12}}>Co-powered by Yatra Technologies</p>
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
    <section className="home-section wrap setup-section"><div className="section-heading"><div><p className="eyebrow">From download to first hello</p><h2>A clear place to start.</h2></div><a className="text-link" href="/docs/install-windows">Setup guide with screenshots ↗</a></div><div className="setup-steps">{[
      ['1','Download the beta','Get the official Windows installer. Read the unsigned-app notice and check the published checksum.'],
      ['2','Connect your provider','Bring your own supported AI provider key. Provider pricing and usage limits apply separately.'],
      ['3','Make yourself at home','Choose your microphone and speakers. Keep Full Access off while you learn the controls.'],
    ].map(([n,title,body])=><div key={n}><span className="step-number">{n}</span><h3>{title}</h3><p>{body}</p></div>)}</div></section>
    <section className="home-section wrap faq-section"><div><p className="eyebrow">Before you bring her home</p><h2>A few honest answers.</h2><p>Zaya is still growing. Here’s what to expect from this release.</p></div><div className="faq-list">{[
      ['Is Zaya ready for everyone?','This is an early Windows beta for a small group of testers. Expect bugs. Installation, startup and packaging were checked on the creator’s device; every feature and Windows configuration has not been independently verified.'],
      ['What does it cost?','The current beta download has no charge. You supply your own AI provider credentials; cloud providers can impose usage limits or charge for their services. Optional tools may have separate requirements.'],
      ['Why might Windows show a warning?','This beta has no verified publisher signature. Windows may warn or block it. Use the official download and checksum, and read the installation guide. Never disable antivirus or Smart App Control to use Zaya.'],
      ['Does it update itself?','Unsigned beta updates are installed manually. Download future betas from the official release page. The existing automatic updater accepts signed releases only.'],
      ['What happens to my data?','Zaya keeps local archives and configuration on your computer. Requests, audio or images you send to a cloud AI provider are processed by that provider. Read the privacy guide before enabling additional features.'],
    ].map(([question,answer])=><details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></section>
    <EnterpriseTeaser />
    <section className="home-final wrap"><div><p className="eyebrow">Let’s start small</p><h2>Say hello to Zaya.</h2><p>Try the beta. Tell us what works—and what needs another look.</p></div><div><a className="btn btn-primary" href="/download">Download Windows beta ↗</a><a className="text-link" href="/docs/getting-started">Read the getting-started guide</a></div></section>
  </div>
</div>;
