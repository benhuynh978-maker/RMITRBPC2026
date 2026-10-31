import Reveal from './Reveal.jsx';

export default function StepCard({ n, icon: Icon, title, text, delay, as = 'li' }) {
  return (
    <Reveal as={as} className="step" delay={delay}>
      <div className="step__top">
        <span className="step__num" aria-hidden="true">
          {String(n).padStart(2, '0')}
        </span>
        {Icon && (
          <span className="step__icon" aria-hidden="true">
            <Icon size={22} />
          </span>
        )}
      </div>
      <h3 className="h3">{title}</h3>
      <p>{text}</p>
    </Reveal>
  );
}
