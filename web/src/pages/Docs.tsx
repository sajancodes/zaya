import React, { useState, useMemo } from 'react';
import { DOCS_DATA, DOCS_CATEGORIES, DocItem } from '../data/docsData';
import { canonicalPath } from '../data/seo';
import { WindowsBetaGuide } from '../components/WindowsBetaGuide';

interface DocsProps {
  topic?: string;
  navigate: (path: string) => void;
}

export const Docs: React.FC<DocsProps> = ({ topic = 'getting-started', navigate }) => {
  const [filterQuery, setFilterQuery] = useState('');

  // Normalize topic key
  const normalizedKey = useMemo(() => {
    let key = topic.replace(/^\/docs\/?/, '').replace(/\/$/, '');
    if (!key) key = 'getting-started';
    if (key === 'install/windows' || key === 'install-windows') return 'install-windows';
    if (key === 'install/android' || key === 'install-android') return 'install-android';
    if (key === 'install/source' || key === 'install-source') return 'install-source';
    if (DOCS_DATA[key]) return key;
    // Check if key matches an item id
    const found = Object.values(DOCS_DATA).find((d) => d.id === key);
    return found ? found.id : 'getting-started';
  }, [topic]);

  const currentDoc: DocItem = DOCS_DATA[normalizedKey] || DOCS_DATA['getting-started'];

  // Extract headings for Table of Contents
  const headings = useMemo(() => {
    const lines = currentDoc.content.split('\n');
    const result: { level: number; text: string; id: string }[] = [];
    lines.forEach((line) => {
      const match = line.match(/^(#{2,3})\s+(.*)$/);
      if (match) {
        const level = match[1].length;
        const text = match[2].trim();
        const id = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
        result.push({ level, text, id });
      }
    });
    return result;
  }, [currentDoc]);

  // Render markdown text into clean HTML elements
  const renderFormattedMarkdown = (content: string) => {
    const lines = content.split('\n');
    const elements: React.ReactNode[] = [];
    let inCodeBlock = false;
    let codeBuffer: string[] = [];
    let codeLang = '';

    lines.forEach((line, idx) => {
      if (line.startsWith('```')) {
        if (inCodeBlock) {
          elements.push(
            <pre key={`code-${idx}`} style={{ marginBottom: '20px' }}>
              <code>{codeBuffer.join('\n')}</code>
            </pre>
          );
          codeBuffer = [];
          inCodeBlock = false;
        } else {
          inCodeBlock = true;
          codeLang = line.replace('```', '').trim();
        }
        return;
      }

      if (inCodeBlock) {
        codeBuffer.push(line);
        return;
      }

      if (line.startsWith('# ')) {
        elements.push(
          <h1 key={`h1-${idx}`} className="editorial-title" style={{ fontSize: '38px', color: '#F4FAFF', margin: '30px 0 16px 0' }}>
            {line.replace('# ', '')}
          </h1>
        );
      } else if (line.startsWith('## ')) {
        const title = line.replace('## ', '');
        const id = title.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
        elements.push(
          <h2 key={`h2-${idx}`} id={id} style={{ fontSize: '24px', color: '#DDFBFF', margin: '36px 0 14px 0', borderBottom: '1px solid rgba(73, 223, 255, 0.1)', paddingBottom: '8px' }}>
            {title}
          </h2>
        );
      } else if (line.startsWith('### ')) {
        const title = line.replace('### ', '');
        const id = title.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
        elements.push(
          <h3 key={`h3-${idx}`} id={id} style={{ fontSize: '18px', color: '#49DFFF', margin: '24px 0 10px 0' }}>
            {title}
          </h3>
        );
      } else if (line.startsWith('> ')) {
        elements.push(
          <div
            key={`quote-${idx}`}
            style={{
              padding: '16px 20px',
              backgroundColor: 'rgba(73, 223, 255, 0.08)',
              borderLeft: '3px solid #49DFFF',
              borderRadius: '0 8px 8px 0',
              margin: '20px 0',
              color: '#DDFBFF',
              fontSize: '14px',
              lineHeight: '1.6'
            }}
          >
            {line.replace('> ', '')}
          </div>
        );
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        elements.push(
          <li key={`li-${idx}`} style={{ color: '#8392A6', fontSize: '15px', lineHeight: '1.7', marginLeft: '20px' }}>
            {line.replace(/^[-*]\s+/, '')}
          </li>
        );
      } else if (/^\d+\.\s+/.test(line)) {
        elements.push(
          <div key={`ol-${idx}`} style={{ color: '#8392A6', fontSize: '15px', lineHeight: '1.7', margin: '6px 0 6px 10px' }}>
            {line}
          </div>
        );
      } else if (line.trim() === '---') {
        elements.push(
          <hr key={`hr-${idx}`} style={{ border: 'none', borderTop: '1px solid rgba(73, 223, 255, 0.12)', margin: '30px 0' }} />
        );
      } else if (line.trim() !== '') {
        elements.push(
          <p key={`p-${idx}`} style={{ color: '#8392A6', fontSize: '15px', lineHeight: '1.7', margin: '12px 0' }}>
            {line}
          </p>
        );
      }
    });

    return elements;
  };

  const handleSelectDoc = (docId: string) => {
    navigate(canonicalPath(`/docs/${docId}`));
  };

  return (
    <div style={{ backgroundColor: '#020407', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div
        className="container"
        style={{
          maxWidth: '1440px',
          margin: '0 auto',
          padding: '40px 24px',
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '280px minmax(0, 1fr) 240px',
          gap: '40px'
        }}
      >
        {/* Left Sidebar */}
        <aside
          style={{
            position: 'sticky',
            top: '88px',
            height: 'calc(100vh - 120px)',
            overflowY: 'auto',
            paddingRight: '16px',
            borderRight: '1px solid rgba(73, 223, 255, 0.1)'
          }}
        >
          {/* Docs Filter Input */}
          <div style={{ marginBottom: '20px' }}>
            <input
              type="text"
              placeholder="Filter topics..."
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              style={{
                width: '100%',
                backgroundColor: 'rgba(8, 20, 35, 0.6)',
                border: '1px solid rgba(73, 223, 255, 0.2)',
                borderRadius: '6px',
                padding: '8px 12px',
                color: '#F4FAFF',
                fontSize: '12px',
                outline: 'none'
              }}
            />
          </div>

          {/* Grouped Category Links */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {DOCS_CATEGORIES.map((cat) => {
              const catDocs = Object.values(DOCS_DATA).filter((d) => d.category === cat);
              const visibleDocs = catDocs.filter((d) =>
                d.title.toLowerCase().includes(filterQuery.toLowerCase()) ||
                d.description.toLowerCase().includes(filterQuery.toLowerCase())
              );

              if (visibleDocs.length === 0) return null;

              return (
                <div key={cat}>
                  <div
                    style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '11px',
                      textTransform: 'uppercase',
                      letterSpacing: '1.5px',
                      color: '#49DFFF',
                      marginBottom: '10px'
                    }}
                  >
                    {cat}
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {visibleDocs.map((doc) => {
                      const isSelected = doc.id === currentDoc.id || doc.id === normalizedKey;
                      return (
                        <li key={doc.id}>
                          <a
                            href={canonicalPath('/docs/' + doc.id)}
                            onClick={(e) => { if (!e.ctrlKey && !e.metaKey && !e.shiftKey && !e.altKey) { e.preventDefault(); handleSelectDoc(doc.id); } }}
                            style={{
                              display: 'block',
                              padding: '6px 10px',
                              borderRadius: '6px',
                              fontSize: '13px',
                              color: isSelected ? '#49DFFF' : '#8392A6',
                              backgroundColor: isSelected ? 'rgba(73, 223, 255, 0.12)' : 'transparent',
                              fontWeight: isSelected ? 600 : 400,
                              cursor: 'pointer',
                              transition: 'all 0.15s ease'
                            }}
                            onMouseEnter={(e) => {
                              if (!isSelected) e.currentTarget.style.color = '#F4FAFF';
                            }}
                            onMouseLeave={(e) => {
                              if (!isSelected) e.currentTarget.style.color = '#8392A6';
                            }}
                          >
                            {doc.title}
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Main Content Article */}
        <main style={{ minWidth: 0, paddingBottom: '80px' }}>
          {/* Breadcrumbs */}
          <div style={{ fontSize: '12px', color: '#8392A6', marginBottom: '16px' }}>
            <span>Documentation</span> / <span style={{ color: '#49DFFF' }}>{currentDoc.category}</span> / <span>{currentDoc.title}</span>
          </div>

          <article>
            {normalizedKey === 'install-windows' && <WindowsBetaGuide />}
            {renderFormattedMarkdown(normalizedKey === 'install-windows' ? currentDoc.content.replace('# Windows Installation Guide', '') : currentDoc.content)}
          </article>
        </main>

        {/* Right Table of Contents */}
        <aside
          style={{
            position: 'sticky',
            top: '88px',
            height: 'calc(100vh - 120px)',
            overflowY: 'auto',
            paddingLeft: '16px',
            borderLeft: '1px solid rgba(73, 223, 255, 0.08)'
          }}
        >
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '11px',
              textTransform: 'uppercase',
              letterSpacing: '1.5px',
              color: '#DDFBFF',
              marginBottom: '14px'
            }}
          >
            On This Page
          </div>
          {headings.length === 0 ? (
            <div style={{ fontSize: '12px', color: '#8392A6' }}>No subheadings</div>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {headings.map((h) => (
                <li key={h.id} style={{ marginLeft: h.level === 3 ? '12px' : 0 }}>
                  <a
                    href={`#${h.id}`}
                    style={{
                      fontSize: '12px',
                      color: '#8392A6',
                      lineHeight: '1.4',
                      display: 'block'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#49DFFF')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#8392A6')}
                  >
                    {h.text}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </div>
  );
};
