import Reveal from './Reveal.jsx';

export default function FeatureCard({ icon: Icon, kicker, title, text, delay, className = '', children, as = 'div' }) {
  return (
    <Reveal as={as} className={`card feature ${className}`.trim()} delay={delay}>
      <div className="feature__head">
        {Icon && (
          <span className="feature__icon" aria-hidden="true">
            <Icon size={24} />
          </span>
        )}
        {kicker && <span className="feature__kicker">{kicker}</span>}
      </div>
      <h3 className="h3">{title}</h3>
      {text && <p>{text}</p>}
      {children}
    </Reveal>
  );
}
