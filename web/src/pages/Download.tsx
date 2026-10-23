import React, { useState } from 'react';
import { useReleases } from '../data/useReleases';

export const Download: React.FC<{navigate: (path: string) => void}> = ({navigate}) => {
  const {releases, loading} = useReleases();
  const [channel, setChannel] = useState('Stable');
  const detected = /Android/i.test(navigator.userAgent) ? 'android' : /Linux/i.test(navigator.userAgent) ? 'linux' : 'windows';
  const platforms = [detected, ...['windows', 'linux', 'android'].filter(p => p !== detected)];
  return <section className="section" style={{minHeight:'100vh', paddingTop:60}}>
    <div className="container" style={{maxWidth:1040}}>
      <div className="section-label">Official distribution</div>
      <h1 className="editorial-title">Download Zaya</h1>
      <p>Created by Sajan Rai. Only published artifacts with verified metadata appear here.</p>
      <label>Release channel <select value={channel} onChange={e => setChannel(e.target.value)}><option>Stable</option><option>Beta</option></select></label>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,280px),1fr))',gap:24,marginTop:32}}>
        {platforms.map(platform => {
          const release = releases.find(r => r.platform === platform && r.channel === channel);
          return <article key={platform} className="glass-panel crystal-corner" style={{padding:28,overflowWrap:'anywhere'}}>
            <h2>{platform === 'windows' ? 'Windows' : platform === 'linux' ? 'Linux' : 'Android Companion'}</h2>
            {platform === detected && <p>Suggested for your device</p>}
            {release ? <><p>Version {release.version} · {release.channel}</p><p>{release.filename} · {release.sizeFormatted}</p>
              <p>{release.date}</p><a className="btn btn-primary" href={release.downloadUrl}>Download for {platform}</a>
              <p style={{fontSize:12,marginTop:20}}>SHA-256<br/><code>{release.sha256}</code></p>
              <button onClick={() => navigator.clipboard.writeText(release.sha256)}>Copy checksum</button>
              <ul>{release.requirements.map(r => <li key={r}>{r}</li>)}</ul></>
              : <p>{loading ? 'Checking published releases…' : `No verified ${channel.toLowerCase()} ${platform} package is published yet.`}</p>}
            {platform === 'windows' && <p>Coding with OpenCode is optional. Signing and clean installation checks are required before the first public Windows release.</p>}
            {platform === 'linux' && <p>Linux packaging is not yet validated. Windows-only computer control features are not promised on Linux.</p>}
            {platform === 'android' && <p>The current companion is the existing owner testing channel. Production signing migration is pending.</p>}
          </article>;
        })}
      </div>
      <p style={{marginTop:32}}>Downloads count clicks, not completed installations. Anonymous installation analytics are optional in Zaya.</p>
      <button className="btn btn-secondary" onClick={() => navigate('/security')}>Release security</button>
    </div>
  </section>;
};
