import React, {useState} from 'react';
import type {ReleaseItem, ReleaseDownload} from '../data/releases';

export const LinuxDownloads:React.FC<{release:ReleaseItem|undefined; loading:boolean}> = ({release,loading}) => {
  const [format,setFormat] = useState('deb');
  const [copied,setCopied] = useState('');
  const fallback:ReleaseDownload[] = release ? [{format:'deb',label:'Ubuntu / Mint',filename:release.filename,
    downloadUrl:release.downloadUrl,sha256:release.sha256,sizeFormatted:release.sizeFormatted,
    commands:['sudo apt install ./'+release.filename,'zaya'],note:'Debian-based AMD64 desktops. Use an X11 session for desktop automation.'}] : [];
  const packages=release?.downloads?.length ? release.downloads : fallback;
  const selected=packages.find(item=>item.format===format) || packages[0];
  return <article className="download-primary linux-download">
    <div className="download-topline"><span className="platform-symbol" aria-hidden="true"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4m-5-9 2 2-2 2m4 0h4"/></svg></span><span className="badge">Linux · {release ? release.channel : 'Coming soon'}</span></div>
    <h2>Linux</h2><p className="platform-description">A familiar presence, on your terms.</p><p className="platform-compatibility">x86-64 · glibc 2.35+ · X11 recommended</p>
    {release && selected ? <>
      <label className="linux-package-picker">Your distribution<select value={selected.format} onChange={event=>{setFormat(event.target.value);setCopied('');}}>{packages.map(item=><option key={item.format} value={item.format}>{item.label} · {item.filename.endsWith('.tar.gz') ? '.tar.gz' : '.'+item.filename.split('.').pop()}</option>)}</select></label>
      <div className="download-file"><span>Version {release.version}</span><span>{selected.sizeFormatted} · x86-64</span></div>
      <a className="btn btn-primary download-main-button" href={selected.downloadUrl} download={selected.filename}>Download for Linux<span aria-hidden="true">↓</span></a>
      <p className="file-note">{selected.filename} · Direct download</p><p className="download-beta-note">Experimental beta · Manual updates</p><details className="download-details"><summary>Installation & requirements</summary><p>{selected.note}</p><p>Use an unlocked Secret Service keyring for credentials. Desktop automation requires X11; Wayland support is limited. Physical microphone/camera and full desktop integration still need real-device testing.</p><div className="linux-install-commands">{selected.commands.map(command=><code key={command}>{command}</code>)}</div><a href="/docs/getting-started">Linux setup guide ↗</a></details>
      <details className="checksum-details download-details"><summary>Verify your download</summary><code>{selected.sha256}</code><button className="small-button" onClick={async()=>{try{await navigator.clipboard.writeText(selected.sha256);setCopied('Checksum copied');}catch{setCopied('Copy the checksum above manually.');}}}>Copy checksum</button><span role="status">{copied}</span></details>
    </> : <><button className="btn btn-primary download-main-button" disabled>Linux download · Coming soon</button><p className="file-note" role="status">{loading ? 'Checking Linux release availability…' : 'No published Linux package is available right now.'}</p></>}
  </article>;
};
