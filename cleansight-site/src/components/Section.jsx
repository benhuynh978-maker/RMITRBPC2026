export default function Section({ id, eyebrow, title, lead, alt = false, children }) {
  const headingId = `${id}-title`;
  return (
    <section id={id} className={`section${alt ? ' section-alt' : ''}`} aria-labelledby={headingId}>
      <div className="container">
        <header>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2 id={headingId}>{title}</h2>
          {lead && <p className="section-lead">{lead}</p>}
        </header>
        {children}
      </div>
    </section>
  );
}
