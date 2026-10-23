import React, { useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { DOCS_DATA, DOCS_CATEGORIES } from '../data/docsData';
import { canonicalPath } from '../data/seo';
import { WindowsBetaGuide } from '../components/WindowsBetaGuide';

const headingId=(text:string)=>text.replace(/[*`]/g,'').toLowerCase().replace(/[^\w\s-]/g,'').replace(/\s+/g,'-');
const textOf=(value:React.ReactNode):string=>React.Children.toArray(value).map(child=>React.isValidElement<{children?:React.ReactNode}>(child)?textOf(child.props.children):String(child)).join('');
export const Docs: React.FC<{topic?:string;navigate:(path:string)=>void}> = ({topic='getting-started'}) => {
  const [query,setQuery]=useState('');
  const requested=topic.replace(/^\/docs\/?/,'').replace(/^install\//,'install-').replace(/\/$/,'') || 'getting-started';
  const key=DOCS_DATA[requested]?requested:Object.keys(DOCS_DATA).find(k=>DOCS_DATA[k].id===requested)||'getting-started';
  const doc=DOCS_DATA[key];
  const headings=[...doc.content.matchAll(/^#{2,3}\s+(.*)$/gm)].map(m=>({title:m[1],id:headingId(m[1])}));
  const sidebar=<><label className="docs-search"><span>Find a topic</span><input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Voice, setup, phone…"/></label>{DOCS_CATEGORIES.map(category=>{const docs=Object.values(DOCS_DATA).filter(d=>d.category===category && (d.title+' '+d.description).toLowerCase().includes(query.toLowerCase()));return docs.length?<div className="docs-group" key={category}><p>{category}</p>{docs.map(d=><a key={d.id} href={canonicalPath('/docs/'+d.id)} aria-current={d.id===doc.id?'page':undefined}>{d.title}</a>)}</div>:null;})}</>;
  return <div className="docs-layout wrap"><aside className="docs-sidebar">{sidebar}</aside><div className="docs-main"><details className="mobile-docs"><summary>Browse documentation</summary>{sidebar}</details><nav className="breadcrumbs" aria-label="Breadcrumb"><a href="/docs/getting-started">Documentation</a><span>/</span><span>{doc.category}</span></nav><article className="prose">
    {key==='install-windows' && <WindowsBetaGuide/>}
    <Markdown remarkPlugins={[remarkGfm]} skipHtml components={{
      a:({href,children})=><a href={href?.startsWith('/')?canonicalPath(href):href}>{children}</a>,
      h2:({children})=><h2 id={headingId(textOf(children))}>{children}</h2>,
      h3:({children})=><h3 id={headingId(textOf(children))}>{children}</h3>,
      table:({children})=><div className="table-scroll"><table>{children}</table></div>,
    }}>{key==='install-windows'?doc.content.replace('# Windows Installation Guide',''):doc.content}</Markdown>
  </article><div className="docs-help"><p>Something unclear or not working?</p><a href="/docs/troubleshooting">Troubleshooting guide ↗</a><a href="mailto:ab4290025@gmail.com">Report a problem ↗</a></div></div><aside className="docs-toc"><p className="eyebrow">On this page</p>{headings.map((h,i)=><a href={'#'+h.id} key={i}>{h.title.replace(/[*`]/g,'')}</a>)}</aside></div>;
};
