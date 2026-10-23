import { useEffect, useState } from 'react';
import type { ReleaseItem } from './releases';

export function useReleases() {
  const [releases, setReleases] = useState<ReleaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/releases', {signal: controller.signal})
      .then(r => { if (!r.ok) throw new Error('Release service unavailable'); return r.json(); })
      .then((rows: any[]) => setReleases(rows.map(r => ({
        version: r.version, tag: r.version, channel: r.channel === 'beta' ? 'Beta' : 'Stable',
        platform: r.platform, platformName: r.platform === 'windows' ? 'Windows Desktop' : r.platform === 'android' ? 'Android Companion' : 'Linux',
        date: new Date(r.published_at * 1000).toLocaleDateString(), filename: r.filename,
        downloadUrl: `/download/${r.platform}?channel=${r.channel || 'stable'}`,
        sha256: r.sha256, sizeBytes: r.size, sizeFormatted: `${(r.size / 1048576).toFixed(1)} MB`,
        highlights: [r.release_notes || 'See official release notes.'], fullChangelog: [r.release_notes || ''],
        requirements: r.platform === 'windows' ? ['Windows 10/11 x64', 'Microphone and internet for cloud providers'] : r.platform === 'android' ? ['Android companion; pairs with Zaya desktop'] : ['See Linux release notes for supported features']
      }))))
      .catch(() => setReleases([])).finally(() => setLoading(false));
    return () => controller.abort();
  }, []);
  return {releases, loading};
}
