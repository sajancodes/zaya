import React, { useEffect, useState } from 'react';
import { AnalyticsMetrics } from '../types';
import { SiteTraffic } from '../components/SiteTraffic';

export const Admin: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [username, setUsername] = useState<string>('owner');
  const [password, setPassword] = useState<string>('');
  const [loginError, setLoginError] = useState<string>('');
  const [metrics, setMetrics] = useState<AnalyticsMetrics | null>(null);
  const [serviceError, setServiceError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [releases, setReleases] = useState<any[]>([]);
  useEffect(() => {
    if (isAuthenticated) fetch('/api/admin/releases').then(r => r.ok ? r.json() : []).then(setReleases).catch(() => setReleases([]));
  }, [isAuthenticated]);

  const fetchMetrics = () => {
    setIsLoading(true);
    setServiceError('');
    fetch('/api/admin/metrics')
      .then((res) => {
        if (res.status === 401) {
          setIsAuthenticated(false);
          throw new Error('Unauthorized');
        }
        if (!res.ok) throw new Error('Admin service unavailable');
        return res.json();
      })
      .then((data) => {
        setMetrics(data);
        setIsAuthenticated(true);
        setIsLoading(false);
      })
      .catch((err) => {
        if (err.message !== 'Unauthorized') setServiceError('Unable to refresh dashboard. Check the connection and try again.');
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (res.ok) {
        setIsAuthenticated(true);
        fetchMetrics();
      } else {
        setLoginError(res.status === 429 ? 'Too many attempts. Wait 5 minutes before trying again.' : res.status === 503 ? 'Admin access is not configured. Set a Production ADMIN_PASSWORD of at least 12 characters and redeploy.' : 'Username or password is incorrect.');
      }
    } catch {
      setLoginError('Could not reach backend.');
    } finally { setIsSubmitting(false); }
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/admin/logout', { method: 'POST' });
    } finally {
      setIsAuthenticated(false);
      setMetrics(null);
    }
  };

  if (!isAuthenticated) {
    return (
      <section className="section" style={{ paddingTop: '80px' }}>
        <div className="container" style={{ maxWidth: '420px' }}>
          <div className="card" style={{ padding: '36px' }}>
            <h1 style={{ fontSize: '22px', color: '#ffffff', marginBottom: '8px', textAlign: 'center' }}>
              Welcome back
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', marginBottom: '24px' }}>
              Sign in to manage releases and view anonymous usage.
            </p>

            <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Username
                </label>
                <input
                  aria-label="Username" autoComplete="username" type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: 'var(--bg-primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '4px',
                    color: '#ffffff',
                    padding: '8px 12px',
                    fontSize: '14px',
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Password
                </label>
                <input
                  aria-label="Password" autoComplete="current-password" type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={{
                    width: '100%',
                    backgroundColor: 'var(--bg-primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '4px',
                    color: '#ffffff',
                    padding: '8px 12px',
                    fontSize: '14px',
                  }}
                  required
                />
              </div>

              {loginError && (
                <div style={{ color: 'var(--accent-red)', fontSize: '13px' }}>
                  {loginError}
                </div>
              )}

              <button disabled={isSubmitting} type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '8px' }}>
                {isSubmitting ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="section" style={{ paddingTop: '40px' }}>
      <div className="container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div className="hero-tag">Owner Dashboard</div>
            <h1 className="section-title" style={{ textAlign: 'left', marginBottom: '4px' }}>
              Overview
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
              Your releases, downloads and installation activity in one place.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button className="btn btn-secondary" onClick={fetchMetrics} disabled={isLoading}>
              {isLoading ? 'Refreshing...' : 'Refresh Stats'}
            </button>
            <button className="btn btn-secondary" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </div>

        <SiteTraffic />
        {metrics && <section className="card admin-releases"><h2>Daily app activity (UTC)</h2>
          <p>Each anonymous installation counts once per day. Opt-in only; reporting starts with version 0.5.1. Earlier versions can also contribute through their existing heartbeats. No historical backfill.</p>
          {metrics.daily_actives?.length ? <table><thead><tr><th>Date</th><th>Active installations</th></tr></thead><tbody>{metrics.daily_actives.map(row => <tr key={row.day}><td>{row.day}</td><td>{row.count}</td></tr>)}</tbody></table> : <p>No daily reports received yet.</p>}
        </section>}
        <section className="admin-releases card"><h2>Release management</h2>
        <p>Deactivate a broken version to stop advertising it. Published binaries remain immutable and are not deleted.</p>
        {releases.map(release => <div className="admin-release-row" key={release.platform + release.version}>
          {release.platform} · {release.version} · {release.channel || 'stable'} · {release.active === false ? 'Pulled' : 'Active'}{' '}
          <button onClick={async () => {
            const active = release.active === false;
            const result = await fetch(`/api/admin/releases/${release.platform}/${release.version}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({active})});
            if (result.ok) setReleases(rows => rows.map(r => r === release ? {...r,active} : r));
          }}>{release.active === false ? 'Reactivate' : 'Stop advertising'}</button>
        </div>)}
        </section>
        {serviceError && <p role="alert" className="admin-error">{serviceError}</p>}
        {metrics && (
          <>
            {/* Top Stat Cards */}
            <div className="metric-grid">
              <div className="metric-card"><div className="metric-label">Active today (UTC)</div><div className="metric-value">{metrics.daily_actives?.find(row => row.day === new Date().toISOString().slice(0, 10))?.count ?? 0}</div><div className="metric-sub">Unique opted-in installations reported today</div></div>
              <div className="metric-card">
                <div className="metric-label">Total Downloads</div>
                <div className="metric-value">{metrics.downloads.total}</div>
                <div className="metric-sub">
                  Windows: {metrics.downloads.windows} · Android: {metrics.downloads.android}
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-label">Retained Installations</div>
                <div className="metric-value">{metrics.installations.total}</div>
                <div className="metric-sub">
                  Windows: {metrics.installations.windows} · Android: {metrics.installations.android}
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-label">Active (Last 24 Hours)</div>
                <div className="metric-value">{metrics.active.last_24h}</div>
                <div className="metric-sub">Installations reporting within 24 hours</div>
              </div>

              <div className="metric-card">
                <div className="metric-label">Active (Last 7 Days)</div>
                <div className="metric-value">{metrics.active.last_7d}</div>
                <div className="metric-sub">30 Days: {metrics.active.last_30d}</div>
              </div>
            </div>

            {/* Split Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))', gap: '24px', marginBottom: '32px' }}>
              {/* Version Adoption */}
              <div className="card">
                <h3 style={{ color: '#ffffff', fontSize: '16px', marginBottom: '16px' }}>Version Adoption</h3>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Version</th>
                      <th>Installs</th>
                      <th>Adoption %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(metrics.version_distribution).map(([ver, count]) => {
                      const pct = metrics.installations.total > 0 ? ((count / metrics.installations.total) * 100).toFixed(1) : '0';
                      return (
                        <tr key={ver}>
                          <td><code>v{ver}</code></td>
                          <td>{count}</td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <div style={{ width: '80px', height: '6px', background: 'var(--border-subtle)', borderRadius: '3px', overflow: 'hidden' }}>
                                <div style={{ width: `${pct}%`, height: '100%', background: 'var(--accent-cyan)' }} />
                              </div>
                              <span>{pct}%</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Daily Install Timeline */}
              <div className="card">
                <h3 style={{ color: '#ffffff', fontSize: '16px', marginBottom: '16px' }}>Daily Registrations (UTC)</h3>
                <p style={{color:'var(--text-muted)', fontSize:12}}>First-seen anonymous IDs, including returns after retention expiry. Earlier history is not backfilled.</p>
                {metrics.daily_installs.length === 0 ? (
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No install history recorded yet.</p>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Registrations</th>
                      </tr>
                    </thead>
                    <tbody>
                      {metrics.daily_installs.map((row) => (
                        <tr key={row.day}>
                          <td>{row.day}</td>
                          <td><b>+{row.count}</b></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Privacy Guarantee Note */}
            <div className="card" style={{marginBottom:24, overflowX:'auto'}}>
              <h3>Recent update health (UTC)</h3>
              <p>{metrics.update_health_definition || 'No production update-health reports received yet.'}</p>
              <table className="data-table"><thead><tr><th>Day / target</th><th>Offered</th><th>Verified downloads</th><th>Installer launches</th><th>Failures</th></tr></thead>
                <tbody>{(metrics.update_health || []).map(row => <tr key={row.day + row.platform + row.target_version}>
                  <td>{row.day} · {row.platform} · {row.target_version || 'unknown'}</td><td>{row.available || 0}</td><td>{row.download_verified || 0}</td><td>{row.installer_started || 0}</td><td>{row.failed || 0}</td>
                </tr>)}</tbody>
              </table>
            </div>
            {metrics.retention && <div className="card" style={{marginBottom:24}}>
              <h3>Retention health</h3>
              <p>Last completed cleanup: {metrics.retention.last_completed ? new Date(metrics.retention.last_completed * 1000).toLocaleString() : 'Not recorded yet'}</p>
              <p>{metrics.retention.limitation}</p>
            </div>}
            <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                🛡️ <b>Privacy Enforcement</b>: This dashboard displays only high-level anonymous metrics.
                Installation IDs are anonymized UUIDv4 tokens without device serials or hardware hashes.
                No prompts, keys, screen text, audio clips, or personal data ever exist in this database.
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
};
