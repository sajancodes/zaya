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
        backgroundColor: 'rgba(2, 4, 7, 0.85)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(73, 223, 255, 0.12)',
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
        {/* Brand & Author */}
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
          <div
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: '#49DFFF',
              boxShadow: '0 0 12px #49DFFF, 0 0 24px rgba(73, 223, 255, 0.6)'
            }}
          />
          <span
            style={{
              fontSize: '20px',
              fontWeight: 700,
              letterSpacing: '3px',
              color: '#F4FAFF',
              fontFamily: "'Inter', sans-serif"
            }}
          >
            ZAYA
          </span>
          <span
            style={{
              fontSize: '11px',
              color: '#8392A6',
              letterSpacing: '0.5px',
              borderLeft: '1px solid rgba(73, 223, 255, 0.15)',
              paddingLeft: '10px',
              display: 'none',
              ...(window.innerWidth > 640 ? { display: 'inline' } : {})
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
              <span
                key={link.path}
                onClick={() => handleNav(link.path)}
                style={{
                  fontSize: '13px',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? '#49DFFF' : '#8392A6',
                  cursor: 'pointer',
                  letterSpacing: '0.3px',
                  transition: 'color 0.15s ease',
                  position: 'relative',
                  padding: '6px 0'
                }}
                onMouseEnter={(e) => {
                  if (!isActive) e.currentTarget.style.color = '#F4FAFF';
                }}
                onMouseLeave={(e) => {
                  if (!isActive) e.currentTarget.style.color = '#8392A6';
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
                      backgroundColor: '#49DFFF',
                      boxShadow: '0 0 8px #49DFFF'
                    }}
                  />
                )}
              </span>
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
                background: 'rgba(73, 223, 255, 0.06)',
                border: '1px solid rgba(73, 223, 255, 0.18)',
                borderRadius: '8px',
                padding: '6px 12px',
                color: '#8392A6',
                fontSize: '12px',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(73, 223, 255, 0.4)';
                e.currentTarget.style.color = '#F4FAFF';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'rgba(73, 223, 255, 0.18)';
                e.currentTarget.style.color = '#8392A6';
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span>Search</span>
              <kbd
                style={{
                  backgroundColor: 'rgba(2, 4, 7, 0.8)',
                  padding: '2px 5px',
                  borderRadius: '4px',
                  fontSize: '10px',
                  border: '1px solid rgba(73, 223, 255, 0.15)'
                }}
              >
                Ctrl+K
              </kbd>
            </button>
          )}

          <button
            onClick={() => handleNav('/download')}
            style={{
              backgroundColor: '#49DFFF',
              color: '#020407',
              border: 'none',
              borderRadius: '8px',
              padding: '8px 18px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 0 20px rgba(73, 223, 255, 0.35)',
              transition: 'all 0.15s ease'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = '0 0 25px rgba(73, 223, 255, 0.6)';
              e.currentTarget.style.transform = 'translateY(-1px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = '0 0 20px rgba(73, 223, 255, 0.35)';
              e.currentTarget.style.transform = 'none';
            }}
          >
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
              color: '#F4FAFF',
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
            backgroundColor: '#050b14',
            borderBottom: '1px solid rgba(73, 223, 255, 0.2)',
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
                color: currentPath === link.path ? '#49DFFF' : '#F4FAFF',
                padding: '6px 0',
                cursor: 'pointer'
              }}
            >
              {link.label}
            </span>
          ))}
          <div style={{ paddingTop: '10px', borderTop: '1px solid rgba(73, 223, 255, 0.1)' }}>
            <span style={{ fontSize: '11px', color: '#8392A6' }}>
              Created and developed by Sajan Rai
            </span>
          </div>
        </div>
      )}
    </nav>
  );
};
