import { DOCS_DATA } from './docsData';

export const PUBLIC_PAGES: Record<string, {title: string; description: string}> = {
  '/enterprise': {title: 'Custom AI Agents & Assistants — Zaya Enterprise | Yatra Technologies', description: 'Discuss custom AI agents, business assistants and workflow integrations with Yatra Technologies. Contact support for an individually scoped project.'},
  '/': {title: 'Zaya AI Assistant — Voice, Desktop & Android | Yatra Technologies', description: 'Meet Zaya, the personal AI assistant by Yatra Technologies: voice conversations, Windows computer control, optional local AI, supervised OpenCode coding and an Android companion.'},
  '/features': {title: 'Zaya AI Assistant Features — Voice, Computer Control & Coding', description: 'Explore Zaya voice assistance, screen understanding, owner-controlled desktop actions, OpenCode coding, local AI options and Android companion calls.'},
  '/docs': {title: 'Zaya Documentation — Setup, Voice & Android Pairing', description: 'Learn how Zaya works: Windows setup, AI providers, voice configuration, Android pairing, optional hand controls and owner permissions.'},
  '/download': {title: 'Download Zaya — Windows Beta & Android Companion', description: 'Try the Zaya Windows beta. Get the official installer, setup screenshots, published checksum and honest beta requirements.'},
  '/releases': {title: 'Zaya Releases — Versions, Checksums & Changes', description: 'Official Zaya release metadata, published platform downloads, version changes and known limitations.'},
  '/roadmap': {title: 'Zaya Roadmap — Planned AI Assistant Improvements', description: 'Follow planned Zaya improvements and current platform limitations. Planned features are distinct from published releases.'},
  '/security': {title: 'Zaya Security — Owner Permissions & Verified Updates', description: 'Understand Zaya owner authorization, credential protection, verified update requirements and release security limitations.'},
  '/privacy': {title: 'Zaya Privacy — Local Data & AI Providers', description: 'How Zaya handles local conversation archives, external AI providers, optional analytics, device pairing and retention.'},
  '/terms': {title: 'Zaya Terms of Use', description: 'Zaya software terms, third-party AI services, user responsibilities and beta limitations.'},
  '/about': {title: 'About Zaya AI Assistant — Yatra Technologies', description: 'Zaya is a personal AI assistant developed by Yatra Technologies. Learn about its voice, desktop, coding and Android companion approach.'},
};

export function canonicalPath(path: string) {
  return path.replace(/^\/docs\/install\//, '/docs/install-').replace(/\/+$/, '') || '/';
}

export function pageMetadata(path: string) {
  path = canonicalPath(path);
  if (path === '/admin') return {title: 'Owner console | Zaya', description: 'Protected Zaya release and analytics dashboard.'};
  if (PUBLIC_PAGES[path]) return PUBLIC_PAGES[path];
  const key = path.replace(/^\/docs\//, '').replace(/^install\//, 'install-');
  const doc = path.startsWith('/docs/') ? DOCS_DATA[key] : undefined;
  return doc ? {title: `${doc.title} | Zaya AI Assistant Docs`, description: doc.description}
    : {title: 'Page not found | Zaya', description: 'This Zaya page does not exist.'};
}

export function pageSchema(path: string, origin: string) {
  path = canonicalPath(path);
  const {title, description} = pageMetadata(path);
  const url = origin + path;
  return {'@context':'https://schema.org', '@graph': [
      {'@type':'WebSite', '@id':origin + '/#website', name:'Zaya AI Assistant', url:origin},
      {'@type':'Organization', '@id':origin + '/about#creator', name:'Yatra Technologies', url:origin + '/about', sameAs:['https://www.instagram.com/yatratech.2/']},
      {'@type':'WebPage', '@id':url + '#page', name:title, description, url, isPartOf:{'@id':origin + '/#website'}},
      ...(path === '/' ? [{'@type':'SoftwareApplication', '@id':origin + '/#zaya', name:'Zaya', alternateName:'Zaya AI Assistant', description, url:origin, applicationCategory:'ProductivityApplication', operatingSystem:'Windows; Android companion', creator:{'@id':origin + '/about#creator'}}] : []),
      ...(path.startsWith('/docs/') ? [{'@type':'BreadcrumbList', itemListElement:[
        {'@type':'ListItem', position:1, name:'Zaya', item:origin + '/'},
        {'@type':'ListItem', position:2, name:'Documentation', item:origin + '/docs'},
        {'@type':'ListItem', position:3, name:title, item:url}
      ]}] : [])
    ]};
}
