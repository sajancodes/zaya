import React, { useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { SearchModal } from './components/SearchModal';
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
import { AnalyticsConsent } from './components/AnalyticsConsent';
import { canonicalPath, pageMetadata, pageSchema } from './data/seo';

export const App: React.FC<{initialPath?: string}> = ({initialPath}) => {
  const [currentPath, setCurrentPath] = useState<string>(initialPath ?? (typeof window === 'undefined' ? '/' : window.location.pathname || '/'));
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);

  useEffect(() => {
    const metadata = pageMetadata(currentPath);
    document.title = metadata.title;
    const url = new URL(canonicalPath(currentPath), import.meta.env.VITE_PUBLIC_SITE_URL || 'https://zayaxyz.vercel.app').href;
    document.querySelector('link[rel="canonical"]')?.setAttribute('href', url);
    for (const [selector, value] of [
      ['meta[name="description"]', metadata.description],
      ['meta[property="og:title"]', metadata.title],
      ['meta[property="og:description"]', metadata.description],
      ['meta[property="og:url"]', url],
    ]) document.querySelector(selector)?.setAttribute('content', value);
    const existing = document.querySelector('script[data-zaya-schema]');
    if (currentPath.startsWith('/admin')) { existing?.remove(); return; }
    const schema = existing ?? document.createElement('script');
    schema.setAttribute('type', 'application/ld+json');
    schema.setAttribute('data-zaya-schema', '');
    schema.textContent = JSON.stringify(pageSchema(currentPath, new URL(url).origin));
    if (!existing) document.head.appendChild(schema);
  }, [currentPath]);

  useEffect(() => {
    const onPopState = () => {
      setCurrentPath(window.location.pathname || '/');
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  // Global Ctrl+K / Cmd+K listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const navigate = (path: string) => {
    if (path.startsWith('/admin') || currentPath.startsWith('/admin')) {
      window.location.assign(path);
      return;
    }
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
      const topic = currentPath.replace(/^\/docs\/?/, '') || 'getting-started';
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

    return <section className="section container"><h1>Page not found</h1><button onClick={() => navigate('/')}>Return to Zaya</button></section>;
  };

  return (
    <div className={currentPath === '/' ? 'site-shell home-shell' : currentPath.startsWith('/admin') ? 'site-shell admin-shell' : 'site-shell'}>
      <Navbar currentPath={currentPath} navigate={navigate} onOpenSearch={() => setIsSearchOpen(true)} />
      <main id="main-content" style={{ flex: 1 }}>
        {renderRoute()}
      </main>
      <Footer navigate={navigate} />
      <AnalyticsConsent path={currentPath}/>

      {/* Global Search Modal */}
      <SearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        navigate={navigate}
      />
    </div>
  );
};
