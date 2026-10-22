import React from 'react';

interface NavbarProps {
  currentPath: string;
  navigate: (path: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentPath, navigate }) => {
  const links = [
    { path: '/features', label: 'Features' },
    { path: '/download', label: 'Download' },
    { path: '/docs/getting-started', label: 'Docs' },
    { path: '/releases', label: 'Releases' },
    { path: '/roadmap', label: 'Roadmap' },
    { path: '/about', label: 'About' },
  ];

  return (
    <header className="navbar">
      <div className="container nav-container">
        <a
          href="/"
          className="nav-brand"
          onClick={(e) => {
            e.preventDefault();
            navigate('/');
          }}
        >
          ZAYA
          <span className="author">Built by Sajan Rai</span>
        </a>

        <ul className="nav-links">
          {links.map((link) => {
            const isActive = currentPath.startsWith(link.path);
            return (
              <li key={link.path}>
                <a
                  href={link.path}
                  className={isActive ? 'active' : ''}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(link.path);
                  }}
                >
                  {link.label}
                </a>
              </li>
            );
          })}
        </ul>

        <div className="nav-cta">
          <button
            className="btn btn-primary"
            onClick={() => navigate('/download')}
          >
            Download Zaya
          </button>
        </div>
      </div>
    </header>
  );
};
