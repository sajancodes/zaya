import React from 'react';
import { ContactIcon, ContactKind } from './ContactIcon';

const contacts: [ContactKind, string, string][] = [
  ['whatsapp', 'WhatsApp · +977 9864393383', 'https://wa.me/9779864393383'],
  ['facebook', 'Facebook', 'https://www.facebook.com/sajan.rai.601665'],
  ['instagram', 'Yatra Technologies on Instagram', 'https://www.instagram.com/yatratech.2/?hl=en'],
  ['github', 'GitHub', 'https://github.com/sajancodes'],
  ['linkedin', 'LinkedIn', 'https://www.linkedin.com/in/sajan-rai-88059938b/'],
  ['email', 'Email support', 'mailto:ab4290025@gmail.com'],
];

export const ContactLinks: React.FC = () => <div className="contact-links">
  {contacts.map(([kind, label, href]) => <a key={href} href={href} aria-label={label} title={label} target="_blank" rel="noopener noreferrer"><ContactIcon kind={kind}/></a>)}
</div>;
