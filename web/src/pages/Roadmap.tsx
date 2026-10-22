import React, { useState } from 'react';
import { ROADMAP_DATA, RoadmapMilestone, RoadmapStatus } from '../data/roadmap';

export const Roadmap: React.FC = () => {
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [activeMilestone, setActiveMilestone] = useState<RoadmapMilestone | null>(null);

  const filtered = ROADMAP_DATA.filter((m) => {
    if (selectedStatus === 'ALL') return true;
    return m.status === selectedStatus;
  });

  const getStatusBadge = (status: RoadmapStatus) => {
    switch (status) {
      case 'SHIPPED':
        return <span className="badge badge-stable">Shipped</span>;
      case 'IN DEVELOPMENT':
        return <span className="badge badge-beta">In Development</span>;
      case 'EXPERIMENTAL':
        return <span className="badge badge-experimental">Experimental</span>;
      case 'PLANNED':
        return <span className="badge badge-planned">Planned</span>;
      case 'RESEARCH':
        return (
          <span
            className="badge"
            style={{
              backgroundColor: 'rgba(52, 120, 255, 0.15)',
              color: '#93c5fd',
              border: '1px solid rgba(52, 120, 255, 0.3)'
            }}
          >
            Research
          </span>
        );
    }
  };

  return (
    <section className="section" style={{ minHeight: '100vh', paddingTop: '60px' }}>
      <div className="container" style={{ maxWidth: '960px' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', maxWidth: '780px', margin: '0 auto 60px auto' }}>
          <div className="section-label">Evolution Roadmap</div>
          <h1 className="editorial-title" style={{ fontSize: '48px', marginBottom: '16px' }}>
            The Path Continues Into Darkness
          </h1>
          <p style={{ color: '#8392A6', fontSize: '16px', lineHeight: '1.7' }}>
            Every milestone builds upon the last. From raw acoustic streaming to persistent 3D spatial agency, track what is shipped, active in development, and envisioned for the future.
          </p>

          {/* Status Filter */}
          <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: '8px', marginTop: '24px' }}>
            {['ALL', 'SHIPPED', 'IN DEVELOPMENT', 'EXPERIMENTAL', 'PLANNED', 'RESEARCH'].map((st) => (
              <button
                key={st}
                onClick={() => setSelectedStatus(st)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '16px',
                  fontSize: '11px',
                  fontFamily: "'JetBrains Mono', monospace",
                  cursor: 'pointer',
                  border: selectedStatus === st ? '1px solid #49DFFF' : '1px solid rgba(73, 223, 255, 0.15)',
                  backgroundColor: selectedStatus === st ? 'rgba(73, 223, 255, 0.15)' : 'transparent',
                  color: selectedStatus === st ? '#49DFFF' : '#8392A6'
                }}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {/* Vertical Destiny Path Spine & Milestones */}
        <div style={{ position: 'relative', paddingLeft: '32px' }}>
          {/* Continuous Glowing Cyan Line */}
          <div
            style={{
              position: 'absolute',
              top: '10px',
              bottom: '10px',
              left: '11px',
              width: '2px',
              background: 'linear-gradient(to bottom, #49DFFF 0%, rgba(73, 223, 255, 0.5) 70%, transparent 100%)',
              boxShadow: '0 0 10px rgba(73, 223, 255, 0.4)'
            }}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
            {filtered.map((m) => (
              <div
                key={m.id}
                onClick={() => setActiveMilestone(m)}
                className="glass-panel"
                style={{
                  padding: '28px',
                  cursor: 'pointer',
                  position: 'relative'
                }}
              >
                {/* Node point along spine */}
                <div
                  style={{
                    position: 'absolute',
                    top: '32px',
                    left: '-29px',
                    width: '14px',
                    height: '14px',
                    borderRadius: '50%',
                    backgroundColor: m.status === 'SHIPPED' ? '#49DFFF' : '#3478FF',
                    border: '3px solid #020407',
                    boxShadow: '0 0 10px #49DFFF'
                  }}
                />

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <span style={{ fontSize: '11px', fontFamily: "'JetBrains Mono', monospace", color: '#49DFFF' }}>
                    {m.quarter}
                  </span>
                  {getStatusBadge(m.status)}
                </div>

                <h3 style={{ fontSize: '20px', color: '#F4FAFF', fontWeight: 600, marginBottom: '8px' }}>
                  {m.title}
                </h3>
                <p style={{ margin: 0, fontSize: '14px', color: '#8392A6', lineHeight: '1.6', marginBottom: '16px' }}>
                  {m.summary}
                </p>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {m.deliverables.map((d) => (
                    <span
                      key={d}
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        backgroundColor: 'rgba(73, 223, 255, 0.06)',
                        border: '1px solid rgba(73, 223, 255, 0.15)',
                        fontSize: '11px',
                        color: '#DDFBFF'
                      }}
                    >
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Final Trailing Element */}
        <div
          style={{
            marginTop: '60px',
            textAlign: 'center',
            color: 'rgba(73, 223, 255, 0.6)',
            fontSize: '13px',
            fontFamily: "'JetBrains Mono', monospace"
          }}
        >
          // The Destiny Path continues into research and discovery.
        </div>
      </div>

      {/* Milestone Modal */}
      {activeMilestone && (
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
          onClick={() => setActiveMilestone(null)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '560px',
              backgroundColor: '#050b14',
              border: '1px solid rgba(73, 223, 255, 0.3)',
              boxShadow: '0 25px 60px rgba(0, 0, 0, 0.9)',
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
                  {activeMilestone.quarter}
                </span>
                <h3 style={{ margin: 0, color: '#F4FAFF', fontSize: '20px', fontWeight: 600 }}>
                  {activeMilestone.title}
                </h3>
              </div>
              <button
                onClick={() => setActiveMilestone(null)}
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

            <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <p style={{ margin: 0, color: '#F4FAFF', fontSize: '14px', lineHeight: '1.6' }}>
                {activeMilestone.summary}
              </p>

              <div>
                <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                  Scope & Deliverables
                </h4>
                <ul style={{ margin: 0, paddingLeft: '18px', color: '#8392A6', fontSize: '13px', lineHeight: '1.6' }}>
                  {activeMilestone.details.map((item, idx) => (
                    <li key={idx} style={{ marginBottom: '6px' }}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div
              style={{
                padding: '16px 24px',
                backgroundColor: '#020407',
                borderTop: '1px solid rgba(73, 223, 255, 0.1)',
                display: 'flex',
                justifyContent: 'flex-end'
              }}
            >
              <button
                onClick={() => setActiveMilestone(null)}
                className="btn btn-secondary"
                style={{ padding: '6px 14px', fontSize: '12px' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
