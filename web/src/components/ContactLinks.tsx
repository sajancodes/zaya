import React from 'react';

const contacts = [
  ['WhatsApp · +977 9864393383', 'https://wa.me/9779864393383'],
  ['Facebook', 'https://www.facebook.com/sajan.rai.601665'],
  ['Instagram', 'https://www.instagram.com/sajancodes/?hl=en'],
  ['GitHub', 'https://github.com/sajancodes'],
  ['LinkedIn', 'https://www.linkedin.com/in/sajan-rai-88059938b/'],
];

export const ContactLinks: React.FC = () => <div className="contact-links">
  {contacts.map(([label, href]) => <a key={href} href={href} target="_blank" rel="noopener noreferrer">{label} <span aria-hidden="true">↗</span></a>)}
</div>;
