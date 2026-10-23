import React from 'react';
import { ContactIcon, ContactKind } from './ContactIcon';

const contacts: [ContactKind, string, string][] = [
  ['whatsapp', 'WhatsApp · +977 9864393383', 'https://wa.me/9779864393383'],
  ['facebook', 'Facebook', 'https://www.facebook.com/sajan.rai.601665'],
  ['instagram', 'Instagram', 'https://www.instagram.com/sajancodes/?hl=en'],
  ['github', 'GitHub', 'https://github.com/sajancodes'],
  ['linkedin', 'LinkedIn', 'https://www.linkedin.com/in/sajan-rai-88059938b/'],
];

export const ContactLinks: React.FC = () => <div className="contact-links">
  {contacts.map(([kind, label, href]) => <a key={href} href={href} target="_blank" rel="noopener noreferrer"><ContactIcon kind={kind}/><span>{label}</span><span className="contact-arrow" aria-hidden="true">↗</span></a>)}
</div>;
