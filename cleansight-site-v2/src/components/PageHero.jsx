import Reveal from './Reveal.jsx';

export default function PageHero({ eyebrow, title, lead, children }) {
  return (
    <header className="page-hero">
      <div className="page-hero__bg" aria-hidden="true" />
      <div className="container">
        <Reveal className="page-hero__inner">
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h1 className="display display--page">{title}</h1>
          {lead && <p className="lead lead--hero">{lead}</p>}
          {children}
        </Reveal>
      </div>
    </header>
  );
}
