import React from 'react';

export type ContactKind = 'whatsapp' | 'facebook' | 'instagram' | 'github' | 'linkedin' | 'email';

export const ContactIcon: React.FC<{kind: ContactKind}> = ({kind}) => <svg className={`contact-icon contact-icon-${kind}`} width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
  {kind === 'instagram' && <g stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".85" fill="currentColor" stroke="none"/></g>}
  {kind === 'facebook' && <path fill="currentColor" d="M14 22v-9h3l.5-3.5H14V7.3c0-1 .3-1.8 1.8-1.8H18V2.4a24 24 0 0 0-2.9-.2c-2.9 0-4.8 1.8-4.8 5v2.3H7V13h3.3v9H14Z"/>}
  {kind === 'whatsapp' && <g stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round"><path d="M20.8 11.5a8.8 8.8 0 0 1-13 7.8L3 20.7l1.4-4.6a8.8 8.8 0 1 1 16.4-4.6Z"/><path d="m8.2 7.2 1.5 2.5-1 1.2a7.6 7.6 0 0 0 4.3 4l1.1-1.3 2.7 1.3c.2 2-1.8 2.5-3.4 1.9-4-1.4-6.6-4.1-7-7.2-.2-1.3.5-2.3 1.8-2.4Z"/></g>}
  {kind === 'github' && <path fill="currentColor" d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.86c-2.78.6-3.37-1.18-3.37-1.18-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.89 1.52 2.34 1.08 2.91.83.09-.65.35-1.08.64-1.33-2.22-.25-4.55-1.11-4.55-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.6 9.6 0 0 1 5 0c1.9-1.29 2.74-1.02 2.74-1.02.55 1.38.2 2.4.1 2.65.64.7 1.03 1.59 1.03 2.68 0 3.84-2.33 4.69-4.56 4.94.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2Z"/>}
  {kind === 'linkedin' && <g fill="currentColor"><rect x="3" y="8.5" width="3.5" height="12" rx=".4"/><circle cx="4.75" cy="4.75" r="2"/><path d="M9 8.5h3.3v1.6c.7-1.1 1.8-1.9 3.7-1.9 3.3 0 4.5 2.1 4.5 5.3v7H17v-6.3c0-1.8-.4-2.9-2-2.9-1.7 0-2.5 1.2-2.5 3v6.2H9v-12Z"/></g>}
  {kind === 'email' && <g stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="2.5" y="4.5" width="19" height="15" rx="2.5"/><path d="m3.5 6 8.5 7 8.5-7"/></g>}
</svg>;
