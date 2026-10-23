import React, { useEffect, useState } from 'react';

export const AnalyticsConsent: React.FC<{path:string}> = ({path}) => {
  const id = (import.meta as any).env.VITE_GA_MEASUREMENT_ID || '';
  const [consent, setConsent] = useState(() => localStorage.getItem('zaya-site-analytics') || 'unset');
  useEffect(() => {
    if (consent !== 'yes' || !/^G-[A-Z0-9]+$/.test(id)) return;
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
  if (!/^G-[A-Z0-9]+$/.test(id)) return null;
  return <aside style={{position:'fixed',bottom:12,left:12,maxWidth:350,padding:14,zIndex:100,background:'#101725',border:'1px solid #7eabd0',borderRadius:8}}>
    <p>{consent === 'unset' ? 'Allow optional website analytics? Your Zaya conversations and app content are never sent.' : 'Website analytics preference'}</p>
    <button onClick={()=>{localStorage.setItem('zaya-site-analytics','yes');setConsent('yes');}}>Allow</button>{' '}
    <button onClick={()=>{localStorage.setItem('zaya-site-analytics','no');location.reload();}}>Decline / turn off</button>
  </aside>;
};
