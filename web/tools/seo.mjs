import fs from 'node:fs';
import React from 'react';
import { renderToString } from 'react-dom/server';
import { createServer } from 'vite';

const origin = (process.env.VITE_PUBLIC_SITE_URL || 'https://zayaxyz.vercel.app').replace(/\/$/, '');
if (new URL(origin).protocol !== 'https:') throw new Error('Public site URL must use HTTPS');
const escape = s => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const template = fs.readFileSync('dist/index.html', 'utf8');
const server = await createServer({server: {middlewareMode: true}, appType: 'custom', optimizeDeps: {noDiscovery: true, include: []}});
try {
  const { App } = await server.ssrLoadModule('/src/App.tsx');
  const { PUBLIC_PAGES, pageMetadata, pageSchema } = await server.ssrLoadModule('/src/data/seo.ts');
  const { DOCS_DATA } = await server.ssrLoadModule('/src/data/docsData.ts');
  const routes = [...Object.keys(PUBLIC_PAGES), ...Object.keys(DOCS_DATA).map(key => '/docs/' + key)];
  for (const route of routes) {
    const {title, description} = pageMetadata(route);
    const url = origin + route;
    const schema = pageSchema(route, origin);
    let html = template.replace(/<title>.*?<\/title>/, `<title>${escape(title)}</title>`)
      .replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${escape(description)}" />`)
      .replace(/<meta property="og:(?:title|description|url|image)"[^>]*>/g, '');
    html = html.replace('</head>', `<link rel="canonical" href="${escape(url)}" /><meta property="og:title" content="${escape(title)}" /><meta property="og:description" content="${escape(description)}" /><meta property="og:url" content="${escape(url)}" /><meta property="og:image" content="${origin}/assets/standby.png" /><meta name="twitter:card" content="summary_large_image" /><script data-zaya-schema type="application/ld+json">${JSON.stringify(schema).replace(/</g, '\\u003c')}</script></head>`);
    // Render the actual public UI and complete documentation, not crawler-only copy.
    html = html.replace('<div id="root"></div>', () => `<div id="root">${renderToString(React.createElement(App, {initialPath:route}))}</div>`);
    const directory = route === '/' ? 'dist' : 'dist' + route;
    fs.mkdirSync(directory,{recursive:true}); fs.writeFileSync(directory + '/index.html',html);
  }
  fs.writeFileSync('dist/sitemap.xml', `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${routes.map(p => `<url><loc>${escape(origin + p)}</loc></url>`).join('')}</urlset>`);
  // Googlebot and OAI-SearchBot inherit these public crawling rules.
  // Authorization, rather than robots.txt, protects private API data.
  fs.writeFileSync('dist/robots.txt', `User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\nSitemap: ${origin}/sitemap.xml\n`);
  fs.copyFileSync('../version.json', 'dist/app-version.json');
  console.log(`Prerendered ${routes.length} public pages with full visible content.`);
} finally {
  await server.close();
}
