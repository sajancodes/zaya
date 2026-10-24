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
  return <div className="download-page wrap page-space">
    <header className="page-intro"><p className="eyebrow">Your first hello</p><h1>Say hello to Zaya.</h1><p>Choose your desktop: Windows and Linux betas for early testers, plus the Android companion. Official downloads and setup details—all right here.</p></header>
    <div className="download-layout"><article className="download-primary">
      <div className="download-topline"><span className="platform-symbol" aria-hidden="true">⊞</span><span className="badge badge-beta">Windows · Early beta</span></div>
      <h2>Zaya for Windows</h2><p>Voice conversation, desktop help, and your own taskbar companion.</p>
      {windows ? <><div className="download-file"><span>Version {windows.version}</span><span>{windows.sizeFormatted} · 64-bit</span></div><a className="btn btn-primary download-main-button" href={windows.downloadUrl}>Download Windows beta <span aria-hidden="true">↓</span></a><p className="file-note">{windows.filename} · Released {windows.date}</p><div className="notice"><strong>Unsigned beta. A little context before you install.</strong><p>Windows may display an unknown-publisher warning or block installation. Updates are manual. Read the guide before opening the file, and never disable your security software.</p><a href="/docs/install-windows">Installation screenshots & help ↗</a></div><details className="checksum-details"><summary>Verify your download · SHA-256</summary><code>{windows.sha256}</code><button className="small-button" onClick={copyHash}>Copy checksum</button><span role="status">{copied}</span><p>A matching hash confirms the bytes match this published release. It does not replace a publisher signature or a malware scan.</p></details></> : <p role="status">{loading?'Checking the official beta release…':'A Windows beta download is not available right now. Please check the official release notes.'}</p>}
    </article><aside className="download-checklist"><p className="eyebrow">Before you start</p><h2>A few things to have ready.</h2><ul><li><span>01</span><div><strong>A supported computer</strong><p>Windows 10/11 x64 or a modern x86-64 Linux desktop. Choose your package below and check its requirements.</p></div></li><li><span>02</span><div><strong>Your own AI connection</strong><p>A supported provider key and internet for cloud features. Provider costs and quotas are separate.</p></div></li><li><span>03</span><div><strong>A microphone & speakers</strong><p>Choose your devices in setup. Camera, phone pairing and Coding Skill are optional.</p></div></li></ul><a className="text-link" href="/docs/getting-started">Walk through your first setup ↗</a></aside></div>
    <section className="other-platforms"><div><p className="eyebrow">Alongside your desktop</p><h2>Want to connect your phone?</h2><p>The Android companion connects to Zaya on your laptop. The current APK is an owner-testing channel, with production signing migration still pending.</p><div className="action-row">{android?<a className="btn btn-secondary" href={android.downloadUrl}>Android companion · {android.version} ↗</a>:<a className="text-link" href="https://github.com/sajancodes/zaya-companion-releases/releases">Check Android release availability ↗</a>}<a className="text-link" href="/docs/install-android">Pairing & installation guide</a></div></div><LinuxDownloads release={linux} loading={loading} /></section>
    <p className="download-footnote">Start with a small test project and keep Full Access off while learning. <a href="/security">Read the security notes</a> · <a href="/releases">All releases</a></p>
  </div>;
};
