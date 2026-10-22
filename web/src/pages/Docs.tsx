import React from 'react';
import { DOCS_DATA } from '../data/docsData';

interface DocsProps {
  topic?: string;
  navigate: (path: string) => void;
}

export const Docs: React.FC<DocsProps> = ({ topic = 'getting-started', navigate }) => {
  const activeArticle = DOCS_DATA[topic] || DOCS_DATA['getting-started'];

  const categories = [
    {
      name: 'Getting Started',
      items: [
        { id: 'getting-started', label: 'Introduction & Setup' },
        { id: 'api-key', label: 'Obtaining an API Key' },
        { id: 'windows-installation', label: 'Windows Installation' },
        { id: 'android-installation', label: 'Android Companion' },
      ],
    },
    {
      name: 'Core Systems',
      items: [
        { id: 'voice', label: 'Voice & Audio Control' },
        { id: 'vision', label: 'Vision & Screen Perception' },
        { id: 'virtual-keyboard', label: 'Virtual Hand Keyboard' },
        { id: 'spatial-workspace', label: 'Spatial 3D Workspace' },
        { id: 'phone-pairing', label: 'Phone Pairing & Calls' },
        { id: 'whatsapp', label: 'WhatsApp Integration' },
        { id: 'automation', label: 'Scheduled Automations' },
      ],
    },
    {
      name: 'Maintenance & Security',
      items: [
        { id: 'troubleshooting', label: 'Troubleshooting Guide' },
        { id: 'uninstall', label: 'Uninstalling Zaya' },
      ],
    },
  ];

  return (
    <div className="container docs-layout">
      {/* Sidebar */}
      <aside className="docs-sidebar">
        {categories.map((cat) => (
          <div key={cat.name} className="docs-nav-group">
            <div className="docs-nav-title">{cat.name}</div>
            <ul className="docs-nav-list">
              {cat.items.map((item) => (
                <li key={item.id}>
                  <a
                    href={`/docs/${item.id}`}
                    className={activeArticle.id === item.id ? 'active' : ''}
                    onClick={(e) => {
                      e.preventDefault();
                      navigate(`/docs/${item.id}`);
                    }}
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </aside>

      {/* Content */}
      <article className="docs-content">
        <div
          dangerouslySetInnerHTML={{
            __html: activeArticle.content
              // Basic markdown formatting
              .replace(/### (.*?)\n/g, '<h3>$1</h3>')
              .replace(/## (.*?)\n/g, '<h2>$1</h2>')
              .replace(/# (.*?)\n/g, '<h1>$1</h1>')
              .replace(/> \*\*(.*?)\*\*: (.*?)\n/g, '<div class="callout"><b>$1:</b> $2</div>')
              .replace(/```text\n([\s\S]*?)```/g, '<div class="code-block"><pre>$1</pre></div>')
              .replace(/`([^`]+)`/g, '<code>$1</code>')
              .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
              .replace(/\*([^*]+)\*/g, '<i>$1</i>')
              .replace(/\n\n/g, '<p></p>')
          }}
        />
      </article>
    </div>
  );
};
