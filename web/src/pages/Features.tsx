import React, { useState } from 'react';
import { FEATURES, FEATURE_CATEGORIES, FeatureItem } from '../data/features';

export const Features: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeFeature, setActiveFeature] = useState<FeatureItem | null>(null);

  const filteredFeatures = FEATURES.filter((feat) => {
    const matchesCategory = selectedCategory === 'All' || feat.category.toLowerCase() === selectedCategory.toLowerCase();
    const matchesSearch =
      feat.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      feat.shortDescription.toLowerCase().includes(searchQuery.toLowerCase()) ||
      feat.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
      feat.dependencies.some((d) => d.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCategory && matchesSearch;
  });

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'STABLE': return 'badge-stable';
      case 'BETA': return 'badge-beta';
      case 'EXPERIMENTAL': return 'badge-experimental';
      default: return 'badge-planned';
    }
  };

  const getPrivacyBadgeClass = (privacy: string) => {
    return privacy === 'LOCAL' ? 'badge-local' : 'badge-cloud';
  };

  return (
    <section className="section" style={{ minHeight: '100vh', paddingTop: '60px' }}>
      <div className="container">
        {/* Header */}
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 40px auto' }}>
          <div className="section-label">Feature Directory</div>
          <h1 className="editorial-title" style={{ fontSize: '48px', marginBottom: '16px' }}>
            Complete Capability Encyclopedia
          </h1>
          <p style={{ color: '#8392A6', fontSize: '16px', lineHeight: '1.7' }}>
            Inspect every native tool, sensory pipeline, model integration, and operating system actuator implemented in Zaya.
          </p>
        </div>

        {/* Search & Category Filter */}
        <div
          style={{
            maxWidth: '1000px',
            margin: '0 auto 40px auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}
        >
          {/* Search Box */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: 'rgba(8, 20, 35, 0.6)',
              border: '1px solid rgba(73, 223, 255, 0.2)',
              borderRadius: '10px',
              padding: '12px 18px',
              gap: '12px'
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#49DFFF" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              placeholder="Search by capability, dependency, or keywords..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: '#F4FAFF',
                fontSize: '15px',
                fontFamily: "'Inter', sans-serif"
              }}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#8392A6',
                  cursor: 'pointer'
                }}
              >
                ✕
              </button>
            )}
          </div>

          {/* Category Tabs Scroll */}
          <div
            style={{
              display: 'flex',
              gap: '8px',
              overflowX: 'auto',
              paddingBottom: '8px',
              scrollbarWidth: 'thin'
            }}
          >
            {FEATURE_CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                style={{
                  whiteSpace: 'nowrap',
                  padding: '6px 14px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  letterSpacing: '0.5px',
                  fontFamily: "'JetBrains Mono', monospace",
                  cursor: 'pointer',
                  border: selectedCategory === cat ? '1px solid #49DFFF' : '1px solid rgba(73, 223, 255, 0.15)',
                  backgroundColor: selectedCategory === cat ? 'rgba(73, 223, 255, 0.15)' : 'transparent',
                  color: selectedCategory === cat ? '#49DFFF' : '#8392A6',
                  transition: 'all 0.15s ease'
                }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Results Counter */}
        <div style={{ maxWidth: '1000px', margin: '0 auto 20px auto', fontSize: '13px', color: '#8392A6' }}>
          Showing <strong>{filteredFeatures.length}</strong> capabilities in <strong>{selectedCategory}</strong>
        </div>

        {/* Feature Cards Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(310px, 1fr))',
            gap: '20px',
            maxWidth: '1000px',
            margin: '0 auto'
          }}
        >
          {filteredFeatures.map((feat) => (
            <div
              key={feat.id}
              onClick={() => setActiveFeature(feat)}
              className="glass-panel"
              style={{
                padding: '24px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}
            >
              <div>
                {/* Badges Bar */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
                  <span className={`badge ${getStatusBadgeClass(feat.status)}`}>
                    {feat.status}
                  </span>
                  <span className={`badge ${getPrivacyBadgeClass(feat.privacy)}`}>
                    {feat.privacy}
                  </span>
                  <span className="badge" style={{ backgroundColor: 'rgba(255,255,255,0.06)', color: '#8392A6', border: '1px solid rgba(255,255,255,0.1)' }}>
                    {feat.platform}
                  </span>
                </div>

                <h3 style={{ fontSize: '16px', color: '#F4FAFF', fontWeight: 600, marginBottom: '8px' }}>
                  {feat.name}
                </h3>
                <p style={{ margin: 0, fontSize: '13px', color: '#8392A6', lineHeight: '1.6', marginBottom: '16px' }}>
                  {feat.shortDescription}
                </p>
              </div>

              <div>
                <div style={{ fontSize: '11px', color: 'rgba(73, 223, 255, 0.7)', fontFamily: "'JetBrains Mono', monospace", borderTop: '1px solid rgba(73, 223, 255, 0.1)', paddingTop: '10px' }}>
                  Deps: {feat.dependencies.join(', ')}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Feature Detail Modal */}
      {activeFeature && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(2, 4, 7, 0.85)',
            backdropFilter: 'blur(12px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px'
          }}
          onClick={() => setActiveFeature(null)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '580px',
              backgroundColor: '#050b14',
              border: '1px solid rgba(73, 223, 255, 0.3)',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.9), 0 0 40px rgba(73, 223, 255, 0.15)',
              borderRadius: '16px',
              overflow: 'hidden'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: '24px',
                borderBottom: '1px solid rgba(73, 223, 255, 0.12)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}
            >
              <div>
                <span style={{ fontSize: '11px', color: '#49DFFF', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  {activeFeature.category}
                </span>
                <h3 style={{ margin: 0, color: '#F4FAFF', fontSize: '20px', fontWeight: 600 }}>
                  {activeFeature.name}
                </h3>
              </div>
              <button
                onClick={() => setActiveFeature(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#8392A6',
                  fontSize: '20px',
                  cursor: 'pointer'
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div>
                <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                  Technical Architecture
                </h4>
                <p style={{ margin: 0, color: '#F4FAFF', fontSize: '14px', lineHeight: '1.6' }}>
                  {activeFeature.detailedDescription}
                </p>
              </div>

              {activeFeature.highlights && (
                <div>
                  <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                    Key Highlights
                  </h4>
                  <ul style={{ margin: 0, paddingLeft: '18px', color: '#8392A6', fontSize: '13px', lineHeight: '1.6' }}>
                    {activeFeature.highlights.map((h) => (
                      <li key={h}>{h}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                  Runtime & System Dependencies
                </h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {activeFeature.dependencies.map((dep) => (
                    <code
                      key={dep}
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        backgroundColor: 'rgba(73, 223, 255, 0.08)',
                        border: '1px solid rgba(73, 223, 255, 0.2)',
                        color: '#49DFFF',
                        fontSize: '12px'
                      }}
                    >
                      {dep}
                    </code>
                  ))}
                </div>
              </div>
            </div>

            <div
              style={{
                padding: '16px 24px',
                backgroundColor: '#020407',
                borderTop: '1px solid rgba(73, 223, 255, 0.1)',
                display: 'flex',
                justifyContent: 'flex-end',
                gap: '12px'
              }}
            >
              {activeFeature.docsLink && (
                <a
                  href={activeFeature.docsLink}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: 'rgba(73, 223, 255, 0.15)',
                    border: '1px solid #49DFFF',
                    borderRadius: '6px',
                    color: '#49DFFF',
                    fontSize: '13px',
                    fontWeight: 500
                  }}
                >
                  View Documentation →
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
