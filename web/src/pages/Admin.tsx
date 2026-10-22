import React, { useEffect, useState } from 'react';
import { AnalyticsMetrics } from '../types';

export const Admin: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [username, setUsername] = useState<string>('owner');
  const [password, setPassword] = useState<string>('');
  const [loginError, setLoginError] = useState<string>('');
  const [metrics, setMetrics] = useState<AnalyticsMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchMetrics = () => {
    setIsLoading(true);
    fetch('/api/admin/metrics')
      .then((res) => {
        if (res.status === 401) {
          setIsAuthenticated(false);
          throw new Error('Unauthorized');
        }
        return res.json();
      })
      .then((data) => {
        setMetrics(data);
        setIsAuthenticated(true);
        setIsLoading(false);
      })
      .catch((err) => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
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
        setLoginError('Invalid admin credentials.');
      }
    } catch {
      setLoginError('Could not reach backend.');
    }
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
              Owner Analytics Login
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', marginBottom: '24px' }}>
              Protected dashboard for Sajan Rai. Enter admin credentials to view anonymous analytics.
            </p>

            <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Username
                </label>
                <input
                  type="text"
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
                  type="password"
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

              <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '8px' }}>
                Sign In to Dashboard
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
              Telemetry & Distribution Analytics
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
              Anonymous installation events, download volume, and daily active heartbeats.
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

        {metrics && (
          <>
            {/* Top Stat Cards */}
            <div className="metric-grid">
              <div className="metric-card">
                <div className="metric-label">Total Downloads</div>
                <div className="metric-value">{metrics.downloads.total}</div>
                <div className="metric-sub">
                  Windows: {metrics.downloads.windows} · Android: {metrics.downloads.android}
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-label">Unique Installations</div>
                <div className="metric-value">{metrics.installations.total}</div>
                <div className="metric-sub">
                  Windows: {metrics.installations.windows} · Android: {metrics.installations.android}
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-label">Active (Last 24 Hours)</div>
                <div className="metric-value">{metrics.active.last_24h}</div>
                <div className="metric-sub">Daily active heartbeats</div>
              </div>

              <div className="metric-card">
                <div className="metric-label">Active (Last 7 Days)</div>
                <div className="metric-value">{metrics.active.last_7d}</div>
                <div className="metric-sub">30 Days: {metrics.active.last_30d}</div>
              </div>
            </div>

            {/* Split Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '24px', marginBottom: '32px' }}>
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
                <h3 style={{ color: '#ffffff', fontSize: '16px', marginBottom: '16px' }}>Recent Daily Installs</h3>
                {metrics.daily_installs.length === 0 ? (
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>No install history recorded yet.</p>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>New Installs</th>
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
