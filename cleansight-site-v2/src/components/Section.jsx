import Reveal from './Reveal.jsx';

export function SectionHeader({ id, eyebrow, title, lead, align = 'left', children }) {
  return (
    <Reveal className={`section-header section-header--${align}`}>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h2 id={id} className="h2">
        {title}
      </h2>
      {lead && <p className="lead">{lead}</p>}
      {children}
    </Reveal>
  );
}

/** Page section with optional alt background. Pass `titleId` so the region is labelled by its heading. */
export default function Section({ id, titleId, alt = false, tight = false, className = '', children }) {
  const cls = ['section', alt && 'section--alt', tight && 'section--tight', className].filter(Boolean).join(' ');
  return (
    <section id={id} className={cls} aria-labelledby={titleId}>
      <div className="container">{children}</div>
    </section>
  );
}
