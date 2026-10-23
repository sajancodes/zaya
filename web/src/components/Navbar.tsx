import React, { useState } from 'react';

interface NavbarProps {
  currentPath: string;
  navigate: (path: string) => void;
  onOpenSearch?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentPath, navigate, onOpenSearch }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { label: 'System', path: '/' },
    { label: 'Features', path: '/features' },
    { label: 'Architecture', path: '/docs/architecture' },
    { label: 'Providers', path: '/docs/providers' },
    { label: 'Docs', path: '/docs' },
    { label: 'Releases', path: '/releases' },
    { label: 'Roadmap', path: '/roadmap' },
  ];

  const handleNav = (path: string) => {
    navigate(path);
    setMobileMenuOpen(false);
  };

  return (
    <nav
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        backgroundColor: 'rgba(1, 4, 9, 0.82)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(95, 234, 255, 0.14)',
        height: '68px',
        display: 'flex',
        alignItems: 'center'
      }}
    >
      <div
        className="container"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '0 24px'
        }}
      >
        {/* Brand & Author using REAL existing Zaya Logo */}
        <div
          onClick={() => handleNav('/')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            cursor: 'pointer',
            userSelect: 'none'
          }}
        >
          <img
            src="/assets/zaya-logo.png"
            alt="Zaya Logo"
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              border: '1px solid rgba(95, 234, 255, 0.4)',
              boxShadow: '0 0 12px rgba(95, 234, 255, 0.35)',
              objectFit: 'cover'
            }}
          />
          <span
            style={{
              fontSize: '20px',
              fontWeight: 800,
              letterSpacing: '3px',
              color: '#ebfcff',
              fontFamily: "'Inter', sans-serif"
            }}
          >
            ZAYA
          </span>
          <span
            style={{
              fontSize: '11px',
              color: '#8193a6',
              letterSpacing: '0.5px',
              borderLeft: '1px solid rgba(95, 234, 255, 0.18)',
              paddingLeft: '10px',
              display: 'none',
              ...(typeof window !== 'undefined' && window.innerWidth > 640 ? { display: 'inline' } : {})
            }}
          >
            by Sajan Rai
          </span>
        </div>

        {/* Desktop Navigation Links */}
        <div
          className="desktop-nav"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '24px'
          }}
        >
          {navLinks.map((link) => {
            const isActive = currentPath === link.path || (link.path !== '/' && currentPath.startsWith(link.path));
            return (
              <a
                key={link.path}
                href={link.path}
                onClick={(e) => { if (!e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) { e.preventDefault(); handleNav(link.path); } }}
                style={{
                  fontSize: '13px',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? '#5feaff' : '#8193a6',
                  cursor: 'pointer',
                  letterSpacing: '0.3px',
                  transition: 'color 0.2s ease',
                  position: 'relative',
                  padding: '6px 0'
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.color = '#ebfcff';
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.color = '#8193a6';
                }}
              >
                {link.label}
                {isActive && (
                  <span
                    style={{
                      position: 'absolute',
                      bottom: 0,
                      left: 0,
                      right: 0,
                      height: '2px',
                      backgroundColor: '#5feaff',
                      boxShadow: '0 0 8px #5feaff'
                    }}
                  />
                )}
              </a>
            );
          })}
        </div>

        {/* Right Actions: Search + Download */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {onOpenSearch && (
            <button
              onClick={onOpenSearch}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                background: 'rgba(3, 10, 18, 0.65)',
                border: '1px solid rgba(95, 234, 255, 0.18)',
                borderRadius: '8px',
                padding: '6px 12px',
                color: '#8193a6',
                fontSize: '12px',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(95, 234, 255, 0.45)';
                e.currentTarget.style.color = '#ebfcff';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(95, 234, 255, 0.18)';
                e.currentTarget.style.color = '#8193a6';
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span>Search</span>
              <kbd
                style={{
                  backgroundColor: 'rgba(1, 4, 9, 0.8)',
                  padding: '2px 5px',
                  borderRadius: '4px',
                  fontSize: '10px',
                  border: '1px solid rgba(95, 234, 255, 0.15)',
                  color: '#5feaff'
                }}
              >
                Ctrl+K
              </kbd>
            </button>
          )}

          <button
            onClick={() => handleNav('/download')}
            className="btn btn-primary"
            style={{
              padding: '8px 18px',
              fontSize: '13px',
              fontWeight: 600,
              gap: '8px'
            }}
          >
            <img
              src="/assets/ruby-icon.png"
              alt="Ruby Icon"
              style={{ width: '16px', height: '16px', objectFit: 'contain' }}
            />
            Download
          </button>

          {/* Mobile hamburger toggle */}
          <button
            className="mobile-toggle"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{
              display: 'none',
              background: 'transparent',
              border: 'none',
              color: '#ebfcff',
              fontSize: '22px',
              cursor: 'pointer',
              padding: '4px'
            }}
          >
            {mobileMenuOpen ? '✕' : '☰'}
          </button>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div
          style={{
            position: 'absolute',
            top: '68px',
            left: 0,
            right: 0,
            backgroundColor: '#020813',
            borderBottom: '1px solid rgba(95, 234, 255, 0.2)',
            padding: '20px 24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            zIndex: 99
          }}
        >
          {navLinks.map((link) => (
            <span
              key={link.path}
              onClick={() => handleNav(link.path)}
              style={{
                fontSize: '15px',
                color: currentPath === link.path ? '#5feaff' : '#ebfcff',
                padding: '6px 0',
                cursor: 'pointer'
              }}
            >
              {link.label}
            </span>
          ))}
          <div style={{ paddingTop: '10px', borderTop: '1px solid rgba(95, 234, 255, 0.1)' }}>
            <span style={{ fontSize: '11px', color: '#8193a6' }}>
              Created and developed by Sajan Rai
            </span>
          </div>
        </div>
      )}
    </nav>
  );
};
