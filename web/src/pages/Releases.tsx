import React, { useState } from 'react';
import { ReleaseItem } from '../data/releases';
import { useReleases } from '../data/useReleases';

export const Releases: React.FC = () => {
  const {releases: RELEASES_DATA, loading} = useReleases();
  const [selectedPlatform, setSelectedPlatform] = useState<'ALL' | 'windows' | 'android'>('ALL');
  const [copiedSha, setCopiedSha] = useState<string | null>(null);

  if (loading) return <section className="section container"><h1>Releases</h1><p>Loading verified releases…</p></section>;
  if (!RELEASES_DATA.length) return <section className="section container"><h1>Releases</h1><p>No verified releases are available from the release service right now. Please try again later.</p></section>;
  const filteredReleases = RELEASES_DATA.filter((r) => {
    if (selectedPlatform === 'ALL') return true;
    return r.platform === selectedPlatform;
  });

  const handleCopy = (sha: string) => {
    navigator.clipboard.writeText(sha);
    setCopiedSha(sha);
    setTimeout(() => setCopiedSha(null), 2000);
  };

  return (
    <section className="section" style={{ minHeight: '100vh', paddingTop: '60px' }}>
      <div className="container" style={{ maxWidth: '920px' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 50px auto' }}>
          <div className="section-label">Official Releases</div>
          <h1 className="editorial-title" style={{ fontSize: '48px', marginBottom: '16px' }}>
            Changelogs & Version History
          </h1>
          <p style={{ color: '#8392A6', fontSize: '16px', lineHeight: '1.7' }}>
            Granular build notes, architectural enhancements, security disclosures, and verified SHA-256 binary checksums.
          </p>

          {/* Platform Filters */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '24px' }}>
            {(['ALL', 'windows', 'android'] as const).map((plat) => (
              <button
                key={plat}
                onClick={() => setSelectedPlatform(plat)}
                style={{
                  padding: '6px 18px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  fontFamily: "'JetBrains Mono', monospace",
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                  cursor: 'pointer',
                  border: selectedPlatform === plat ? '1px solid #49DFFF' : '1px solid rgba(73, 223, 255, 0.15)',
                  backgroundColor: selectedPlatform === plat ? 'rgba(73, 223, 255, 0.15)' : 'transparent',
                  color: selectedPlatform === plat ? '#49DFFF' : '#8392A6'
                }}
              >
                {plat === 'ALL' ? 'All Platforms' : plat}
              </button>
            ))}
          </div>
        </div>

        {/* Releases Stream */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          {filteredReleases.map((rel: ReleaseItem) => (
            <article
              key={`${rel.platform}-${rel.version}`}
              className="glass-panel"
              style={{ padding: '36px' }}
            >
              {/* Release Header */}
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                  borderBottom: '1px solid rgba(73, 223, 255, 0.12)',
                  paddingBottom: '20px',
                  marginBottom: '24px'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                    <h2 style={{ fontSize: '24px', color: '#F4FAFF', fontWeight: 600, margin: 0 }}>
                      Zaya v{rel.version}
                    </h2>
                    <span className="badge badge-stable">{rel.channel}</span>
                    <span className="badge" style={{ backgroundColor: 'rgba(255,255,255,0.06)', color: '#8392A6', border: '1px solid rgba(255,255,255,0.1)' }}>
                      {rel.platformName}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: '#8392A6' }}>
                    Published on {rel.date} · {rel.sizeFormatted}
                  </div>
                </div>

                <a
                  href={rel.downloadUrl}
                  className="btn btn-primary"
                  style={{ fontSize: '13px', padding: '10px 20px' }}
                >
                  Download {rel.filename}
                </a>
              </div>

              {/* Highlights */}
              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '13px', color: '#DDFBFF', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '10px' }}>
                  Release Highlights
                </h3>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {rel.highlights.map((h, i) => (
                    <li key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px', color: '#DDFBFF' }}>
                      <span style={{ color: '#49DFFF' }}>•</span>
                      {h}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Full Changelog */}
              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '13px', color: '#DDFBFF', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '10px' }}>
                  Detailed Changes
                </h3>
                <ul style={{ paddingLeft: '20px', margin: 0, color: '#8392A6', fontSize: '13px', lineHeight: '1.6' }}>
                  {rel.fullChangelog.map((c, i) => (
                    <li key={i} style={{ marginBottom: '4px' }}>{c}</li>
                  ))}
                </ul>
              </div>

              {/* Known Issues */}
              {rel.knownIssues && rel.knownIssues.length > 0 && (
                <div
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    backgroundColor: 'rgba(245, 158, 11, 0.08)',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    marginBottom: '24px'
                  }}
                >
                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#fbbf24', marginBottom: '6px' }}>
                    Known Operational Considerations:
                  </div>
                  <ul style={{ paddingLeft: '18px', margin: 0, color: '#d1d5db', fontSize: '12px' }}>
                    {rel.knownIssues.map((issue, idx) => (
                      <li key={idx}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Binary Verification Bar */}
              <div
                style={{
                  padding: '12px 16px',
                  backgroundColor: '#020407',
                  borderRadius: '6px',
                  border: '1px solid rgba(73, 223, 255, 0.1)',
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '8px',
                  fontSize: '11px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: '#8392A6' }}>SHA-256:</span>
                  <code style={{ color: '#49DFFF', fontSize: '10px' }}>{rel.sha256}</code>
                </div>
                <span
                  onClick={() => handleCopy(rel.sha256)}
                  style={{ color: '#49DFFF', cursor: 'pointer', fontWeight: 600 }}
                >
                  {copiedSha === rel.sha256 ? '✓ Copied' : 'Copy Hash'}
                </span>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
};
