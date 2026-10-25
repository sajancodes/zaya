import React, { useState } from 'react';
import { FEATURES, FEATURE_CATEGORIES } from '../data/features';
import { CrystalCore } from '../components/CrystalAtmosphere';
import { canonicalPath } from '../data/seo';

const experiences = [
  ['01', 'Speak naturally.', 'Voice', 'Live conversation, interruption and your choice of AI connection.', '/docs/voice'],
  ['02', 'Work in your world.', 'Desktop', 'Screen understanding, browser help and computer controls.', '/docs/computer-control'],
  ['03', 'Build something.', 'Coding', 'Supervised OpenCode sessions with progress you can follow.', '/docs/coding'],
  ['04', 'Stay connected.', 'Phone', 'An optional Android companion for calls, messages and camera sharing.', '/docs/mobile'],
  ['05', 'Go beyond the cursor.', 'Spatial', 'Explore hand tracking, mid-air typing and a 3D workspace.', '/docs/spatial'],
  ['06', 'Keep your own space.', 'Privacy', 'Local archives, deliberate recall and owner-controlled permissions.', '/docs/security'],
];

export const Features: React.FC = () => {
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All');
  const categories = FEATURE_CATEGORIES.filter(c => c === 'All' || FEATURES.some(f => f.category === c));
  const filtered = FEATURES.filter(feature => (category === 'All' || feature.category === category) &&
    [feature.name, feature.category, feature.shortDescription, feature.detailedDescription, ...feature.dependencies].join(' ').toLowerCase().includes(query.trim().toLowerCase()));
  const groups = categories.filter(c => c !== 'All').map(name => ({ name, items: filtered.filter(f => f.category === name) })).filter(g => g.items.length);

  return <div className="wrap features-page premium-features">
    <header className="features-hero"><div className="features-hero-copy">
      <p className="eyebrow">The Zaya universe · Capability guide</p>
      <h1>Many facets.<br /><em>One companion.</em></h1>
      <p>A voice beside you. A helping hand on your desktop. A connection that travels with you. Discover the capabilities that come together in Zaya.</p>
      <div className="action-row"><a className="btn btn-primary" href="#all-features">Explore every feature <span aria-hidden="true">↓</span></a><a className="text-link" href="/download">Get to know Zaya ↗</a></div>
      <div className="feature-stats"><div><strong>{FEATURES.length}</strong><span>catalogued capabilities</span></div><div><strong>{categories.length - 1}</strong><span>connected categories</span></div><div><strong>You</strong><span>in control</span></div></div>
    </div><CrystalCore /></header>

    <section className="experience-section" aria-labelledby="experiences-title">
      <div className="section-heading"><div><p className="eyebrow">A little possibility, everywhere</p><h2 id="experiences-title">Find your facet.</h2></div><p>Begin with the everyday. Explore the advanced when you’re ready. Each capability has its own requirements.</p></div>
      <div className="experience-grid">{experiences.map(([number, title, label, body, href]) => <a className="experience-card" href={href} key={number}>
        <div className="experience-card-top"><span>{number} / {label}</span><span className="facet-mark" aria-hidden="true">◇</span></div><h3>{title}</h3><p>{body}</p><span className="experience-link">Explore {label.toLowerCase()} <span aria-hidden="true">↗</span></span>
      </a>)}</div>
    </section>

    <section id="all-features" className="all-features" aria-labelledby="catalog-title">
      <div className="section-heading"><div><p className="eyebrow">Nothing hidden behind the crystal</p><h2 id="catalog-title">The complete feature collection.</h2></div><p>Browse all {FEATURES.length} catalogued capabilities. Development labels describe components; they do not certify every flow in the public beta. Planned features are not available yet.</p></div>
      <div className="feature-filter-panel"><div className="catalog-controls">
        <label><span>Find a feature</span><input type="search" placeholder="Try voice, files, calls…" value={query} onChange={e => setQuery(e.target.value)} /></label>
        <label><span>Category</span><select value={category} onChange={e => setCategory(e.target.value)}>{categories.map(c => <option key={c}>{c}</option>)}</select></label>
        {(query || category !== 'All') && <button className="btn btn-secondary" onClick={() => { setQuery(''); setCategory('All'); }}>Clear filters</button>}
      </div><p className="catalog-count" role="status">Showing {filtered.length} of {FEATURES.length} capabilities</p></div>
      {groups.length === 0 && <div className="feature-empty"><h3>No matching facets.</h3><p>Try another search or clear your filters to explore the full collection.</p></div>}
      {groups.map(group => <section className="feature-group" key={group.name} aria-label={`${group.name} features`}>
        <div className="feature-group-heading"><h3>{group.name}</h3><span>{String(group.items.length).padStart(2, '0')} capabilities</span><div /></div>
        <div className="feature-card-grid">{group.items.map(feature => <article className="feature-card" key={feature.id} data-feature-id={feature.id}>
          <div className="feature-card-meta"><span className={`feature-status status-${feature.status.toLowerCase()}`}>{feature.status.toLowerCase()}</span><span>{feature.platform.toLowerCase()}</span></div>
          <h4>{feature.name}</h4><p>{feature.shortDescription}</p>
          <div className="feature-data-route"><span aria-hidden="true">◇</span> Data route: {feature.privacy.toLowerCase()}</div>
          <details><summary>Details & requirements <span aria-hidden="true">+</span></summary><p>{feature.detailedDescription}</p>{feature.highlights?.length ? <ul>{feature.highlights.map(highlight => <li key={highlight}>{highlight}</li>)}</ul> : null}<p><strong>Requires:</strong> {feature.dependencies.join(', ') || 'See documentation.'}</p></details>
          {feature.docsLink && <a className="text-link" href={canonicalPath(feature.docsLink)}>Read the guide ↗</a>}
        </article>)}</div>
      </section>)}
    </section>
    <div className="premium-cta"><span className="cta-crystal" aria-hidden="true">◇</span><p className="eyebrow">Your first hello</p><h2>Bring a little ice<br /><em>to your everyday.</em></h2><p>Start with the Windows beta. Choose your provider, set your permissions and make Zaya your own.</p><a className="btn btn-primary" href="/download">Get the Windows beta ↗</a></div>
  </div>;
};
