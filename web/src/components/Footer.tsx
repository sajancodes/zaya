import React from 'react';

interface FooterProps {
  navigate: (path: string) => void;
}

export const Footer: React.FC<FooterProps> = ({ navigate }) => {
  return (
    <footer className="footer">
      <div className="container footer-content">
        <div>
          <div style={{ fontWeight: 700, color: '#ffffff', letterSpacing: '1px', marginBottom: '4px' }}>
            ZAYA
          </div>
          <div>Created and developed by Sajan Rai. Private, spatial, autonomous.</div>
        </div>

        <ul className="footer-links">
          <li>
            <a href="/download" onClick={(e) => { e.preventDefault(); navigate('/download'); }}>
              Download
            </a>
          </li>
          <li>
            <a href="/docs/getting-started" onClick={(e) => { e.preventDefault(); navigate('/docs/getting-started'); }}>
              Documentation
            </a>
          </li>
          <li>
            <a href="/privacy" onClick={(e) => { e.preventDefault(); navigate('/privacy'); }}>
              Privacy Policy
            </a>
          </li>
          <li>
            <a href="/terms" onClick={(e) => { e.preventDefault(); navigate('/terms'); }}>
              Terms
            </a>
          </li>
          <li>
            <a href="/security" onClick={(e) => { e.preventDefault(); navigate('/security'); }}>
              Security
            </a>
          </li>
          <li>
            <a href="/admin" onClick={(e) => { e.preventDefault(); navigate('/admin'); }}>
              Admin
            </a>
          </li>
        </ul>
      </div>
    </footer>
  );
};
