import React, { useState } from 'react';
import { useReleases } from '../data/useReleases';
import { LinuxDownloads } from '../components/LinuxDownloads';

export const Download: React.FC<{navigate:(path:string)=>void}> = () => {
  const {releases,loading}=useReleases();
  const [copied,setCopied]=useState('');
  const windows=releases.find(r=>r.platform==='windows' && r.channel==='Beta');
  const linux=releases.find(r=>r.platform==='linux' && r.channel==='Stable') || releases.find(r=>r.platform==='linux');
  const android=releases.find(r=>r.platform==='android' && r.channel==='Stable');
  const copyHash=async()=>{try{await navigator.clipboard.writeText(windows?.sha256 || '');setCopied('Checksum copied');}catch{setCopied('Copy the checksum below manually.');}};
  return <div className="download-page download-refined wrap page-space">
    <header className="page-intro"><p className="eyebrow">Download Zaya</p><h1>Make room for Zaya.</h1><p>Choose your desktop. Download Zaya. Make her your own.</p></header>
    <div className="desktop-downloads" aria-label="Desktop downloads">
      <article className="download-primary">
        <div className="download-topline"><span className="platform-symbol" aria-hidden="true"><svg width="25" height="25" viewBox="0 0 24 24" fill="currentColor"><path d="M2 4 11 2.7V11H2zm11-1.6L22 1v10h-9zM2 13h9v8.3L2 20zm11 0h9v10l-9-1.4z"/></svg></span><span className="badge badge-beta">Early beta</span></div>
        <h2>Windows</h2><p className="platform-description">Your everyday desktop companion.</p>
        <p className="platform-compatibility">Windows 10 or 11 · 64-bit</p><div className="download-installer">Your package<strong>Windows installer · .exe</strong></div>
        {windows ? <>
          <div className="download-file"><span>Version {windows.version}</span><span>{windows.sizeFormatted}</span></div>
          <a className="btn btn-primary download-main-button" href={windows.downloadUrl} download={windows.filename}>Download for Windows <span aria-hidden="true">↓</span></a>
          <p className="file-note">{windows.filename} · Direct download</p>
          <p className="download-beta-note">Unsigned beta · Manual updates</p>
          <details className="download-details"><summary>Installation help</summary><p>Windows may show an unknown-publisher warning or block installation. Read the installation guide before opening the file. Never disable your security software.</p><a href="/docs/install-windows">Windows setup guide ↗</a></details>
          <details className="checksum-details download-details"><summary>Verify your download</summary><p>SHA-256 confirms the file matches this release. It does not replace a publisher signature or malware scan.</p><code>{windows.sha256}</code><button className="small-button" onClick={copyHash}>Copy checksum</button><span role="status">{copied}</span></details>
        </> : <p role="status">{loading?'Checking Windows availability…':'Windows download is temporarily unavailable. Please check release notes.'}</p>}
      </article>
      <LinuxDownloads release={linux} loading={loading} />
    </div>
    <section className="download-companion" aria-label="Android companion"><div className="companion-copy"><span className="eyebrow">Take the conversation with you</span><h2>Meet Zaya on your phone.</h2><p>The Android companion pairs with Zaya on your computer. Owner-testing channel; production signing migration is pending.</p></div><div className="companion-actions">{android ? <a className="btn btn-secondary" href={android.downloadUrl} download={android.filename}>Download Android APK <span aria-hidden="true">↓</span></a> : <span role="status">{loading?'Checking Android availability…':'Android download is temporarily unavailable.'}</span>}<a className="text-link" href="/docs/install-android">Pairing guide ↗</a></div></section>
    <section className="download-essentials" aria-label="Getting started"><div><span>01</span><h3>Bring your AI connection</h3><p>A supported provider key and internet. Provider costs are separate.</p></div><div><span>02</span><h3>Choose your devices</h3><p>A microphone and speakers for voice. Camera and coding tools are optional.</p></div><div><span>03</span><h3>Say your first hello</h3><p>A short setup, then your own companion. <a href="/docs/getting-started">Getting started ↗</a></p></div></section>
    <div className="download-bottom-links"><a href="/releases">Release notes ↗</a><a href="/security">Security & permissions ↗</a><span>Keep Full Access off while getting started.</span></div>
  </div>;
};
