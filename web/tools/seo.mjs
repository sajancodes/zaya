import fs from 'node:fs';
const origin = (process.env.VITE_PUBLIC_SITE_URL || 'https://zayaxyz.vercel.app').replace(/\/$/, '');
const pages = {
  '/': ['Zaya — Personal AI Assistant for Desktop & Android', 'Voice, computer control, optional local AI and supervised coding. Created by Sajan Rai.'],
  '/features': ['Zaya features', 'Explore voice, hand control, screen perception, coding and Android companion features.'],
  '/docs': ['Zaya setup and documentation', 'Configure providers, voice, Android pairing and optional hand controls.'],
  '/download': ['Download Zaya', 'Published Windows, Linux and Android packages, checksums and requirements.'],
  '/releases': ['Zaya releases and changes', 'Verified release metadata, versions and known limitations.'],
  '/roadmap': ['Zaya roadmap', 'Planned improvements and platform limitations.'],
  '/security': ['Zaya security', 'Signatures, verified updates, owner permissions and privacy controls.'],
  '/privacy': ['Zaya privacy policy', 'Local data, optional analytics, provider interactions and retention.'],
  '/terms': ['Zaya terms', 'Software responsibilities, third-party providers and beta limitations.'],
  '/about': ['About Zaya — Created by Sajan Rai', 'The personal assistant project and its creator.']
};
const escape = s => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const template = fs.readFileSync('dist/index.html', 'utf8');
for (const [route, [title, description]] of Object.entries(pages)) {
  const url = origin + route;
  const schema = JSON.stringify({'@context':'https://schema.org','@type':route === '/' ? 'SoftwareApplication' : 'WebPage', name:title, description, url,
    ...(route === '/' ? {applicationCategory:'ProductivityApplication', operatingSystem:'Windows; Android', creator:{'@type':'Person',name:'Sajan Rai'}} : {})});
  let html = template.replace(/<title>.*?<\/title>/, `<title>${escape(title)}</title>`)
    .replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${escape(description)}" />`)
    .replace(/<meta property="og:(?:title|description|url|image)"[^>]*>/g, '');
  html = html.replace('</head>', `<link rel="canonical" href="${url}" /><meta property="og:title" content="${escape(title)}" /><meta property="og:description" content="${escape(description)}" /><meta property="og:url" content="${url}" /><meta property="og:image" content="${origin}/assets/standby.png" /><meta name="twitter:card" content="summary_large_image" /><script type="application/ld+json">${schema}</script></head>`);
  html = html.replace('<div id="root"></div>', `<div id="root"><main><h1>${escape(title)}</h1><p>${escape(description)}</p><nav>${Object.keys(pages).map(p => `<a href="${p}">${escape(pages[p][0])}</a>`).join(' ')}</nav></main></div>`);
  const directory = route === '/' ? 'dist' : 'dist' + route;
  fs.mkdirSync(directory,{recursive:true}); fs.writeFileSync(directory + '/index.html',html);
}
fs.writeFileSync('dist/sitemap.xml', `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${Object.keys(pages).map(p => `<url><loc>${origin}${p}</loc></url>`).join('')}</urlset>`);
fs.writeFileSync('dist/robots.txt', `User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\nSitemap: ${origin}/sitemap.xml\n`);
fs.copyFileSync('../version.json', 'dist/app-version.json');
