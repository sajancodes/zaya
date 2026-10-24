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
    <h2>Zaya for Linux</h2><p>Choose your distribution’s package. These x86-64 builds require glibc 2.35 or newer.</p>
    {release && selected ? <>
      <div className="linux-formats" role="group" aria-label="Linux distribution and package format">{packages.map(item=><button key={item.format} type="button" aria-pressed={selected.format===item.format} onClick={()=>{setFormat(item.format);setCopied('');}}>{item.label}<small>{item.filename.endsWith('.tar.gz') ? '.tar.gz' : '.'+item.filename.split('.').pop()}</small></button>)}</div>
      <p className="linux-package-note">{selected.note}</p>
      <div className="download-file"><span>Version {release.version}</span><span>{selected.sizeFormatted} · x86-64</span></div>
      <a className="btn btn-primary download-main-button" href={selected.downloadUrl}>Download {selected.label}<span aria-hidden="true">↓</span></a>
      <p className="file-note">{selected.filename}</p>
      <details className="checksum-details"><summary>Verify this package · SHA-256</summary><code>{selected.sha256}</code><button className="small-button" onClick={async()=>{try{await navigator.clipboard.writeText(selected.sha256);setCopied('Checksum copied');}catch{setCopied('Copy the checksum above manually.');}}}>Copy checksum</button><span role="status">{copied}</span></details>
      <p>Install / launch:</p><div className="linux-install-commands">{selected.commands.map(command=><code key={command}>{command}</code>)}</div>
      <div className="notice"><strong>Experimental unsigned Linux beta.</strong><p>Use an unlocked Secret Service keyring for credentials. Desktop automation requires X11; Wayland support is limited. Physical microphone/camera and full desktop integration still need real-device testing. Updates are manual.</p></div>
    </> : <><button className="btn btn-primary download-main-button" disabled>Linux download · Coming soon</button><p className="file-note" role="status">{loading ? 'Checking Linux release availability…' : 'No published Linux package is available right now.'}</p></>}
    <a className="text-link" href="/releases">Linux release notes & requirements ↗</a>
  </article>;
};
