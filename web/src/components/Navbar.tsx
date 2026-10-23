import React, { useState } from 'react';
import { CoffeeSupport } from './CoffeeSupport';
export const Navbar: React.FC<{currentPath:string; navigate:(path:string)=>void; onOpenSearch?:()=>void}> = ({currentPath,onOpenSearch}) => {
  const [open,setOpen] = useState(false);
  const [coffeeOpen,setCoffeeOpen] = useState(false);
  const links=[['Features','/features'],['Enterprise','/enterprise'],['Getting started','/docs/getting-started'],['Release notes','/releases']];
  return <header className="site-header"><a className="skip-link" href="#main-content">Skip to content</a><nav className="wrap nav-inner" aria-label="Main navigation">
    <div className="nav-brand-stack"><a className="site-brand" href="/" aria-label="Zaya home"><img src="/assets/zaya-logo.png" alt="" width="34" height="34"/><span>Zaya</span></a><div className="coffee-hanger"><span className="coffee-string" aria-hidden="true"/><button aria-label="Buy me a coffee" className="coffee-trigger" onClick={()=>setCoffeeOpen(true)}><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M4 8h13v7a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V8ZM17 9h2a3 3 0 0 1 0 6h-2M8 2v3m5-3v3"/></svg><span className="coffee-card-copy"><span>Buy me a</span><strong>coffee</strong></span><span className="coffee-card-heart" aria-hidden="true">♡</span></button></div></div>
    <div className="nav-links">{links.map(([label,path])=><a key={path} href={path} aria-current={currentPath===path?'page':undefined}>{label}</a>)}</div>
    <div className="nav-actions"><button className="icon-button" aria-label="Search documentation" onClick={onOpenSearch}><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg></button><a className="btn btn-primary nav-download" href="/download">Get Zaya <span aria-hidden="true">↗</span></a><button className="menu-toggle icon-button" aria-label={open?'Close navigation':'Open navigation'} aria-expanded={open} aria-controls="mobile-navigation" onClick={()=>setOpen(!open)}>{open?'×':'☰'}</button></div>
    {open && <div className="mobile-navigation" id="mobile-navigation">{links.map(([label,path])=><a key={path} href={path} onClick={()=>setOpen(false)}>{label}</a>)}<a href="/download">Download the beta ↗</a><button onClick={()=>{setOpen(false);onOpenSearch?.();}}>Search documentation</button></div>}
  </nav>{coffeeOpen && <CoffeeSupport onClose={()=>setCoffeeOpen(false)}/>}</header>;
};
