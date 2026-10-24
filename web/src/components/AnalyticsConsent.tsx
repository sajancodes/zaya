import React, { useEffect, useState } from 'react';
import {preference, privacySignal, setPreference, trackPage, trackDownload} from '../data/siteAnalytics';

export const AnalyticsConsent: React.FC<{path:string}> = ({path}) => {
  const id = (import.meta as any).env.VITE_GA_MEASUREMENT_ID || '';
  const [consent, setConsent] = useState(() => typeof window === 'undefined' ? 'unset' : preference());
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    const sync = (event: StorageEvent) => { if(event.key === 'zaya-site-analytics') { if(preference() !== 'yes') location.reload(); else setConsent(preference()); } };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, []);
  useEffect(() => {
    trackPage(path);
    if (path.startsWith('/admin') || consent !== 'yes' || privacySignal()) return;
    const onClick = (event: MouseEvent) => trackDownload(event, path);
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, [consent, path]);
  useEffect(() => {
    if (path.startsWith('/admin') || consent !== 'yes' || privacySignal() || !/^G-[A-Z0-9]+$/.test(id)) return;
    const win = window as any;
    if (!win.gtag) {
      win.dataLayer = win.dataLayer || [];
      win.gtag = function(){win.dataLayer.push(arguments);};
      win.gtag('js',new Date());
      win.gtag('config',id,{send_page_view:false,allow_google_signals:false,allow_ad_personalization_signals:false});
      const script=document.createElement('script'); script.async=true;
      script.src=`https://www.googletagmanager.com/gtag/js?id=${id}`; document.head.appendChild(script);
    }
    // Never include query strings, search phrases, referrers or app content.
    win.gtag('event','page_view',{page_location:location.origin + path,page_referrer:''});
  },[consent,id,path]);
  if (path.startsWith('/admin') || privacySignal()) return null;
  if (consent !== 'unset' && !expanded) return <button className="analytics-preferences" onClick={()=>setExpanded(true)}>Analytics preferences</button>;
  return <aside className="site-consent" aria-label="Website analytics preferences">
    <strong>Help improve Zaya?</strong><p>Allow anonymous visit, page and download-click reports, with broad device and traffic-source categories? Your conversations and app content are never included.{/^G-[A-Z0-9]+$/.test(id) ? ' Google Analytics is also enabled only with your permission.' : ''} <a href="/privacy">Privacy details</a></p>
    <div><button onClick={()=>{setPreference('yes');setConsent(preference());setExpanded(false);}}>Allow analytics</button>
    <button onClick={()=>{setPreference('no');setConsent('no');location.reload();}}>Decline / turn off</button></div>
  </aside>;
};
