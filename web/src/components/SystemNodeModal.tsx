import React from 'react';
import { SystemNode } from '../data/architecture';

interface SystemNodeModalProps {
  node: SystemNode | null;
  onClose: () => void;
  navigate: (path: string) => void;
}

export const SystemNodeModal: React.FC<SystemNodeModalProps> = ({ node, onClose, navigate }) => {
  if (!node) return null;

  return (
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
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '560px',
          backgroundColor: '#050b14',
          border: '1px solid rgba(73, 223, 255, 0.3)',
          boxShadow: '0 25px 60px rgba(0, 0, 0, 0.9), 0 0 40px rgba(73, 223, 255, 0.15)',
          borderRadius: '16px',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
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
            <span
              style={{
                fontSize: '11px',
                textTransform: 'uppercase',
                letterSpacing: '1.5px',
                color: '#49DFFF',
                display: 'block',
                marginBottom: '4px'
              }}
            >
              Layer: {node.layer}
            </span>
            <h3 style={{ margin: 0, color: '#F4FAFF', fontSize: '20px', fontWeight: 600 }}>
              {node.name}
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#8392A6',
              fontSize: '20px',
              cursor: 'pointer',
              padding: '4px'
            }}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div>
            <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
              Subsystem Overview
            </h4>
            <p style={{ margin: 0, color: '#F4FAFF', fontSize: '14px', lineHeight: '1.6' }}>
              {node.description}
            </p>
          </div>

          <div>
            <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
              Source Modules & Components
            </h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {node.keyFiles.map((file) => (
                <code
                  key={file}
                  style={{
                    backgroundColor: 'rgba(73, 223, 255, 0.08)',
                    border: '1px solid rgba(73, 223, 255, 0.2)',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    color: '#49DFFF',
                    fontSize: '12px',
                    fontFamily: "'JetBrains Mono', monospace"
                  }}
                >
                  {file}
                </code>
              ))}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                Tech Stack
              </h4>
              <ul style={{ margin: 0, paddingLeft: '18px', color: '#8392A6', fontSize: '13px' }}>
                {node.techStack.map((tech) => (
                  <li key={tech}>{tech}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 style={{ color: '#DDFBFF', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
                Protocols
              </h4>
              <ul style={{ margin: 0, paddingLeft: '18px', color: '#8392A6', fontSize: '13px' }}>
                {node.protocols.map((proto) => (
                  <li key={proto}>{proto}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Footer */}
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
          <button
            onClick={() => {
              onClose();
              navigate('/docs/architecture');
            }}
            style={{
              padding: '8px 16px',
              backgroundColor: 'rgba(73, 223, 255, 0.15)',
              border: '1px solid #49DFFF',
              borderRadius: '6px',
              color: '#49DFFF',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer'
            }}
          >
            Read Architecture Docs →
          </button>
        </div>
      </div>
    </div>
  );
};
