import assert from 'node:assert/strict';
import fs from 'node:fs';

const sitemap = fs.readFileSync('dist/sitemap.xml','utf8');
const urls = [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map(m => m[1]);
assert(urls.length > 20, 'Documentation must be individually discoverable');
const titles = new Set();
for (const url of urls) {
  const route = new URL(url).pathname;
  assert(!/^\/(admin|api)(\/|$)/.test(route));
  const html = fs.readFileSync(`dist${route === '/' ? '' : route}/index.html`, 'utf8');
  const title = html.match(/<title>(.*?)<\/title>/)?.[1];
  assert(title && !titles.has(title), `Missing or duplicate title: ${route}`);
  titles.add(title);
  assert(html.includes(`rel="canonical" href="${url}"`), `Canonical: ${route}`);
  assert(html.includes('<h1'), `Visible page heading: ${route}`);
  assert(html.includes('href="/docs/getting-started"'), `Crawlable navigation: ${route}`);
  const schema = JSON.parse(html.match(/<script data-zaya-schema type="application\/ld\+json">(.*?)<\/script>/s)[1]);
  assert(schema['@graph'].some(item => item['@type'] === 'WebPage' && item.url === url));
  if (route.startsWith('/docs/')) assert(html.includes('<article>') && html.includes('BreadcrumbList'));
  assert(!html.includes('zaya.sajan.codes'), `Stale origin: ${route}`);
  for (const [, href] of html.matchAll(/href="(\/[^"?#]*)/g)) {
    if (href.startsWith('/assets/') || href === '/favicon.ico') continue;
    assert(urls.includes(new URL(href, url).href), `Broken public navigation: ${route} -> ${href}`);
  }
}
assert(fs.readFileSync('dist/robots.txt','utf8').includes('User-agent: *\nAllow: /'));
const home = fs.readFileSync('dist/index.html','utf8');
assert(home.includes('google-site-verification'));
const gettingStarted = fs.readFileSync('dist/docs/getting-started/index.html','utf8');
assert(gettingStarted.includes('unsigned Windows testing release'));
assert(gettingStarted.includes('Stable Windows releases are not available yet'));
const windowsGuide = fs.readFileSync('dist/docs/install-windows/index.html','utf8');
assert(windowsGuide.includes('Do not turn off antivirus, Smart App Control'));
for (const name of ['options', 'ready', 'first-run']) {
  const image = `/assets/install/windows-beta-${name}.png`;
  assert(windowsGuide.includes(image) && fs.statSync(`dist${image}`).size > 1000, `Missing actual installation screenshot: ${name}`);
}
console.log(`SEO proof passed for ${urls.length} public pages: unique metadata, canonical URLs, rendered content, links, schema and sitemap.`);
