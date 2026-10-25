import React, { useState, useEffect, useRef } from 'react';
import { FEATURES } from '../data/features';
import { PROVIDERS } from '../data/providers';
import { RELEASES_DATA } from '../data/releases';
import { ARCHITECTURE_NODES } from '../data/architecture';

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  navigate: (path: string) => void;
}

interface SearchResult {
  id: string;
  title: string;
  category: string;
  type: 'Feature' | 'Doc' | 'Provider' | 'Architecture' | 'Release';
  description: string;
  path: string;
}

export const SearchModal: React.FC<SearchModalProps> = ({ isOpen, onClose, navigate }) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      const previousFocus = document.activeElement as HTMLElement | null;
      const focusTimer = setTimeout(() => inputRef.current?.focus(), 50);
      setQuery('');
      setSelectedIndex(0);
      return () => {
        clearTimeout(focusTimer);
        if (previousFocus?.isConnected) previousFocus.focus();
      };
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (isOpen) {
          onClose();
        } else {
          // Trigger open if parent listens or handles it
        }
      } else if (e.key === 'Escape' && isOpen) {
        onClose();
      } else if (e.key === 'Tab' && isOpen) {
        const controls = dialogRef.current?.querySelectorAll<HTMLElement>('button, input, a[href], [tabindex="0"]');
        if (!controls?.length) return;
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault(); last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault(); first.focus();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Aggregate searchable items
  const allItems: SearchResult[] = [
    // Features
    ...FEATURES.map((f) => ({
      id: f.id,
      title: f.name,
      category: f.category,
      type: 'Feature' as const,
      description: f.shortDescription,
      path: f.docsLink || '/features'
    })),
    // Providers
    ...PROVIDERS.map((p) => ({
      id: p.id,
      title: p.name,
      category: p.category,
      type: 'Provider' as const,
      description: p.description,
      path: '/docs/providers'
    })),
    // Architecture
    ...ARCHITECTURE_NODES.map((a) => ({
      id: a.id,
      title: a.name,
      category: a.layer,
      type: 'Architecture' as const,
      description: a.summary,
      path: '/docs/architecture'
    })),
    // Core Documentation Routes
    {
      id: 'doc-getting-started',
      title: 'Getting Started Guide',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Step-by-step setup walkthrough from download to first command.',
      path: '/docs/getting-started'
    },
    {
      id: 'doc-windows',
      title: 'Windows Installation & DPAPI',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Requirements, installer paths, and local credential encryption.',
      path: '/docs/install/windows'
    },
    {
      id: 'doc-voice',
      title: 'Voice Architecture & Gemini Live',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Full-duplex WebSocket streaming, VAD interruption, and ducking.',
      path: '/docs/voice'
    },
    {
      id: 'doc-hand-control',
      title: 'Optical Hand Control & Air Keyboard',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Isolated MediaPipe hand landmarks, mid-air typing, and gestures.',
      path: '/docs/hand-control'
    },
    {
      id: 'doc-spatial',
      title: '3D Spatial Workspace',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Babylon.js WebGPU canvas, GLB models, and progressive streaming.',
      path: '/docs/spatial'
    },
    {
      id: 'doc-android',
      title: 'Android Mobile Companion',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Native Jetpack Compose companion, voice calls, and phone video.',
      path: '/docs/mobile'
    },
    {
      id: 'doc-whatsapp',
      title: 'WhatsApp Hermes Link & Privacy',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Hermes linked-device session, Observe/Draft/Auto modes, and limits.',
      path: '/docs/whatsapp'
    },
    {
      id: 'doc-security',
      title: 'Security & Trust Boundary',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Owner authority model: external content is DATA, NOT AUTHORITY.',
      path: '/docs/security'
    },
    {
      id: 'doc-privacy',
      title: 'Privacy & Data Storage Matrix',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Granular breakdown: Local vs Provider vs Phone vs WhatsApp.',
      path: '/docs/privacy'
    },
    {
      id: 'doc-missions',
      title: 'Mission Supervisor & Autonomy',
      category: 'Documentation',
      type: 'Doc' as const,
      description: '10-state machine, bounded retries, and SQLite durability.',
      path: '/docs/missions'
    },
    {
      id: 'doc-coding',
      title: 'Supervised OpenCode Orchestrator',
      category: 'Documentation',
      type: 'Doc' as const,
      description: 'Coding briefs, automated testing, and tool-free review passes.',
      path: '/docs/coding'
    },
    // Releases
    ...RELEASES_DATA.map((r) => ({
      id: `release-${r.version}`,
      title: `Zaya v${r.version} (${r.platformName})`,
      category: r.channel,
      type: 'Release' as const,
      description: r.highlights.join(' · '),
      path: '/releases'
    }))
  ];

  const filtered = query.trim() === ''
    ? allItems.slice(0, 8)
    : allItems
        .filter((item) =>
          item.title.toLowerCase().includes(query.toLowerCase()) ||
          item.description.toLowerCase().includes(query.toLowerCase()) ||
          item.category.toLowerCase().includes(query.toLowerCase())
        )
        .slice(0, 10);

  const handleSelect = (item: SearchResult) => {
    onClose();
    navigate(item.path);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(filtered.length, 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % Math.max(filtered.length, 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        handleSelect(filtered[selectedIndex]);
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(2, 4, 7, 0.85)',
        backdropFilter: 'blur(16px)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '12vh'
      }}
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Search Zaya documentation"
        style={{
          width: '100%',
          maxWidth: '640px',
          backgroundColor: 'var(--site-surface)',
          border: '1px solid rgba(73, 223, 255, 0.28)',
          boxShadow: '0 24px 70px rgba(0, 0, 0, 0.2)',
          borderRadius: '12px',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: '16px 20px',
            borderBottom: '1px solid rgba(73, 223, 255, 0.15)',
            gap: '12px'
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--site-accent)" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search capabilities, documentation, providers, or architecture..."
            style={{
              flex: 1,
              minWidth: 0,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--site-ink)',
              fontSize: '16px',
              fontFamily: "'Inter', sans-serif"
            }}
          />
          <kbd
            style={{
              backgroundColor: 'rgba(73, 223, 255, 0.1)',
              border: '1px solid rgba(73, 223, 255, 0.25)',
              borderRadius: '4px',
              padding: '2px 8px',
              fontSize: '11px',
              color: 'var(--site-accent)',
              fontFamily: 'monospace'
            }}
          >
            ESC
          </kbd>
          <button type="button" className="icon-button" aria-label="Close search" onClick={onClose}>×</button>
        </div>

        {/* Results List */}
        <div style={{ maxHeight: '420px', overflowY: 'auto', padding: '8px' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '36px', textAlign: 'center', color: 'var(--site-muted)', fontSize: '14px' }}>
              No matches found for <span style={{ color: 'var(--site-accent)' }}>"{query}"</span>
            </div>
          ) : (
            filtered.map((item, index) => {
              const isSelected = index === selectedIndex;
              return (
                <div
                  key={`${item.type}-${item.id}`}
                  onClick={() => handleSelect(item)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  style={{
                    padding: '12px 16px',
                    borderRadius: '8px',
                    backgroundColor: isSelected ? 'rgba(73, 223, 255, 0.12)' : 'transparent',
                    border: isSelected ? '1px solid rgba(73, 223, 255, 0.3)' : '1px solid transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--site-ink)', fontWeight: 600, fontSize: '14px' }}>
                      {item.title}
                    </span>
                    <span
                      style={{
                        fontSize: '10px',
                        textTransform: 'uppercase',
                        letterSpacing: '1px',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor: 'rgba(52, 120, 255, 0.2)',
                        color: 'var(--site-accent)',
                        border: '1px solid rgba(73, 223, 255, 0.2)'
                      }}
                    >
                      {item.type}
                    </span>
                  </div>
                  <p
                    style={{
                      margin: 0,
                      color: 'var(--site-muted)',
                      fontSize: '12px',
                      lineHeight: '1.4',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}
                  >
                    {item.description}
                  </p>
                </div>
              );
            })
          )}
        </div>

        {/* Footer shortcuts */}
        <div
          style={{
            padding: '10px 16px',
            backgroundColor: 'var(--site-bg)',
            borderTop: '1px solid rgba(73, 223, 255, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '11px',
            color: 'var(--site-muted)'
          }}
        >
          <span>Use <kbd style={{ color: 'var(--site-accent)' }}>↑</kbd> <kbd style={{ color: 'var(--site-accent)' }}>↓</kbd> to navigate</span>
          <span>Press <kbd style={{ color: 'var(--site-accent)' }}>ENTER</kbd> to open</span>
          <span><kbd style={{ color: 'var(--site-accent)' }}>ESC</kbd> to close</span>
        </div>
      </div>
    </div>
  );
};
