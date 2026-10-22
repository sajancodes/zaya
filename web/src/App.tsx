import React, { useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { Home } from './pages/Home';
import { Download } from './pages/Download';
import { Features } from './pages/Features';
import { Docs } from './pages/Docs';
import { Releases } from './pages/Releases';
import { Roadmap } from './pages/Roadmap';
import { Privacy } from './pages/Privacy';
import { Terms } from './pages/Terms';
import { Security } from './pages/Security';
import { About } from './pages/About';
import { Admin } from './pages/Admin';

export const App: React.FC = () => {
  const [currentPath, setCurrentPath] = useState<string>(window.location.pathname || '/');

  useEffect(() => {
    const onPopState = () => {
      setCurrentPath(window.location.pathname || '/');
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const navigate = (path: string) => {
    window.history.pushState(null, '', path);
    setCurrentPath(path);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const renderRoute = () => {
    if (currentPath === '/' || currentPath === '') {
      return <Home navigate={navigate} />;
    }
    if (currentPath === '/download') {
      return <Download navigate={navigate} />;
    }
    if (currentPath === '/features') {
      return <Features />;
    }
    if (currentPath.startsWith('/docs')) {
      const parts = currentPath.split('/').filter(Boolean);
      const topic = parts[1] || 'getting-started';
      return <Docs topic={topic} navigate={navigate} />;
    }
    if (currentPath === '/releases') {
      return <Releases />;
    }
    if (currentPath === '/roadmap') {
      return <Roadmap />;
    }
    if (currentPath === '/privacy') {
      return <Privacy />;
    }
    if (currentPath === '/terms') {
      return <Terms />;
    }
    if (currentPath === '/security') {
      return <Security />;
    }
    if (currentPath === '/about') {
      return <About />;
    }
    if (currentPath === '/admin') {
      return <Admin />;
    }

    // Default fallback to Home
    return <Home navigate={navigate} />;
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar currentPath={currentPath} navigate={navigate} />
      <main style={{ flex: 1 }}>
        {renderRoute()}
      </main>
      <Footer navigate={navigate} />
    </div>
  );
};
