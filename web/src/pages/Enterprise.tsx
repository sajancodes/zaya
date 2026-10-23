import React from 'react';
import { ContactLinks } from '../components/ContactLinks';
import { ContactIcon } from '../components/ContactIcon';

const contact = 'mailto:ab4290025@gmail.com?subject=Custom%20AI%20assistant%20enquiry&body=Hello%20Sajan%2C%0A%0AI%27d%20like%20to%20discuss%20a%20custom%20AI%20agent%20or%20assistant.%0A%0ABusiness%20or%20project%3A%0AWhat%20it%20should%20do%3A%0AExisting%20tools%20to%20connect%3A%0ATimeline%3A%0ABudget%20range%3A%0A';

export const EnterpriseTeaser: React.FC = () => <section className="enterprise-teaser wrap">
  <div><p className="eyebrow">Zaya for your world · Enterprise</p><h2>Your business.<br /><em>Your own AI.</em></h2><p>Have a workflow that deserves its own assistant? Let’s discuss a custom AI agent built around your team, tools and goals.</p><span className="yatra-credit">Co-powered by Yatra Technologies</span></div>
  <div><span className="enterprise-facet" aria-hidden="true">◇</span><a className="btn btn-primary" href="/enterprise">Explore custom AI solutions ↗</a><a className="text-link" href={contact}>Contact support ↗</a></div>
</section>;

export const Enterprise: React.FC = () => <div className="wrap enterprise-page">
  <header className="enterprise-hero"><div><p className="eyebrow">Enterprise · Custom AI development</p><h1>Your vision.<br /><em>Your assistant.</em></h1><p>Make AI part of how your business works. Discuss a custom agent or assistant designed for your workflows, your team and your existing tools.</p><div className="action-row"><a className="btn btn-primary" href={contact}>Discuss your project ↗</a><a className="text-link" href="#enterprise-process">How it works ↓</a></div><div className="enterprise-credit"><span>Created and developed by <strong>Sajan Rai</strong></span><span>Co-powered by <strong>Yatra Technologies</strong></span></div></div>
    <figure className="yatra-art"><img src="/assets/branding/yatra-technologies.png" alt="Yatra Technologies — Your Journey, Our Technology. Web and app development, cloud solutions and innovative ideas." width="1080" height="1080" /><figcaption>Yatra Technologies · Your Journey, Our Technology</figcaption></figure>
  </header>
  <section className="enterprise-offerings" aria-labelledby="enterprise-offerings-title"><div className="section-heading"><div><p className="eyebrow">Built around a real need</p><h2 id="enterprise-offerings-title">More than a generic chatbot.</h2></div><p>Custom projects are scoped and quoted individually. Integrations, deployment, maintenance and data requirements are agreed before work begins.</p></div><div className="experience-grid">{[
    ['01', 'Custom AI assistants', 'Plan a branded voice or chat assistant for your product, internal team or customer experience.'],
    ['02', 'Agents for your workflows', 'Explore agents that help with repeatable business tasks, with appropriate permissions and human review.'],
    ['03', 'Connected experiences', 'Discuss connections to your approved tools and data, plus web, desktop or mobile interfaces suited to the project.'],
  ].map(([number,title,body]) => <article className="experience-card" key={number}><div className="experience-card-top"><span>{number} / Custom development</span><span className="facet-mark" aria-hidden="true">◇</span></div><h3>{title}</h3><p>{body}</p></article>)}</div></section>
  <section id="enterprise-process" className="enterprise-process"><p className="eyebrow">From idea to a clear scope</p><h2>Let’s build the right thing.</h2><div className="setup-steps">{[
    ['1','Tell us the problem','Share what your team does, what slows it down and what a useful result would look like.'],
    ['2','Agree the project','Discuss feasibility, data access, delivery scope, pricing and support expectations.'],
    ['3','Build, review, refine','Work toward an agreed implementation with feedback and validation against your requirements.'],
  ].map(([number,title,body]) => <div key={number}><span className="step-number">{number}</span><h3>{title}</h3><p>{body}</p></div>)}</div></section>
  <section className="premium-cta"><p className="eyebrow">Contact support · Project enquiries</p><h2>What would you<br /><em>like to make?</em></h2><p>Tell Sajan about your use case, integrations, timeline and budget range. Please leave passwords, API keys and private customer data out of your first enquiry.</p><a className="btn btn-primary" href={contact}>Start a conversation ↗</a><a className="enterprise-email" href="mailto:ab4290025@gmail.com"><ContactIcon kind="email"/>ab4290025@gmail.com</a><p className="yatra-credit">Co-powered by Yatra Technologies</p></section>
  <section className="enterprise-contacts" aria-labelledby="contact-title"><p className="eyebrow">Let’s connect</p><h2 id="contact-title">Talk to Sajan.</h2><p>Reach out about a custom AI assistant, a project idea or support.</p><ContactLinks /></section>
</div>;
