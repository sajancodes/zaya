import React, { lazy, Suspense } from 'react';
import { windowsBeta } from '../data/useReleases';
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
    <div className="home-principles wrap"><span>Created by <strong>Sajan Rai</strong></span><span>Voice, desktop & optional coding</span><span>Provider choices. Your permissions.</span></div>
    <section id="meet-zaya" className="home-section wrap">
      <div className="section-heading"><div><p className="eyebrow">A companion with something to do</p><h2>Start with your everyday.</h2></div><p>Three ways to get to know Zaya. These are example requests—not recorded conversations or guaranteed outcomes.</p></div>
      <div className="usecase-list">{examples.map(item=><article className="usecase" key={item.number}><span className="item-number">{item.number}</span><div><h3>{item.title}</h3><p className="example-prompt">{item.prompt}</p></div><div><p>{item.body}</p><a className="text-link" href={item.href}>{item.link} <span aria-hidden="true">↗</span></a></div></article>)}</div>
    </section>
    <section className="home-section wrap"><div className="companion-story"><div className="character-portrait"><img src="/assets/standby.png" alt="Zaya’s ice-and-crystal companion character" loading="lazy"/><span>Same Zaya. Right beside your work.</span></div><div className="story-copy"><p className="eyebrow">More than another chat tab</p><h2>A familiar face.<br/><em>A place on your desktop.</em></h2><p>Zaya’s character sits above your taskbar. Open Settings & Controls when you need them, choose your provider, and make the experience your own.</p><p>The Android companion is an optional testing channel for connecting with your laptop. It isn’t a standalone phone assistant.</p><a className="text-link" href="/features">See capabilities & requirements <span aria-hidden="true">↗</span></a></div></div></section>
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
    <section className="home-final wrap"><div><p className="eyebrow">Let’s start small</p><h2>Say hello to Zaya.</h2><p>Try the beta. Tell us what works—and what needs another look.</p></div><div><a className="btn btn-primary" href="/download">Download Windows beta ↗</a><a className="text-link" href="/docs/getting-started">Read the getting-started guide</a></div></section>
  </div>
</div>;
