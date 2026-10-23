import { useEffect, useState } from 'react';
import type { ReleaseItem } from './releases';
import beta from './windowsBeta.json';

export const windowsBeta: ReleaseItem | null = beta.published ? {
  version: beta.version, tag: beta.tag, channel: 'Beta', platform: 'windows', platformName: 'Windows Desktop',
  date: beta.date, filename: beta.filename, downloadUrl: beta.url, sha256: beta.sha256,
  sizeBytes: beta.size, sizeFormatted: `${(beta.size / 1048576).toFixed(1)} MB`, unsigned: true,
  highlights: ['Unsigned early testing release; manual updates only'], fullChangelog: ['See the linked GitHub release notes.'],
  requirements: ['Windows 10/11 x64', 'Unsigned: some Windows security policies block installation', 'Own provider key and internet for cloud voice features']
} : null;

const includeBeta = (rows: ReleaseItem[]) => windowsBeta ? [...rows.filter(r => !(r.platform === 'windows' && r.channel === 'Beta')), windowsBeta] : rows;

export function useReleases() {
  const [releases, setReleases] = useState<ReleaseItem[]>(includeBeta([]));
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/releases', {signal: controller.signal})
      .then(r => { if (!r.ok) throw new Error('Release service unavailable'); return r.json(); })
      .then((rows: any[]) => setReleases(includeBeta(rows.map(r => ({
        version: r.version, tag: r.version, channel: r.channel === 'beta' ? 'Beta' : 'Stable',
        platform: r.platform, platformName: r.platform === 'windows' ? 'Windows Desktop' : r.platform === 'android' ? 'Android Companion' : 'Linux',
        date: new Date(r.published_at * 1000).toLocaleDateString(), filename: r.filename,
        downloadUrl: `/download/${r.platform}?channel=${r.channel || 'stable'}`,
        sha256: r.sha256, sizeBytes: r.size, sizeFormatted: `${(r.size / 1048576).toFixed(1)} MB`,
        highlights: [r.release_notes || 'See official release notes.'], fullChangelog: [r.release_notes || ''],
        requirements: r.platform === 'windows' ? ['Windows 10/11 x64', 'Microphone and internet for cloud providers'] : r.platform === 'android' ? ['Android companion; pairs with Zaya desktop'] : ['See Linux release notes for supported features']
      })))))
      .catch(() => setReleases(includeBeta([]))).finally(() => setLoading(false));
    return () => controller.abort();
  }, []);
  return {releases, loading};
}
