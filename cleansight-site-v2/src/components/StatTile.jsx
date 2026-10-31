import Reveal from './Reveal.jsx';
import RefMarks from './RefMarks.jsx';

/** Big number + label, with a numbered source superscript. */
export default function StatTile({ value, label, refs, delay, as = 'div' }) {
  return (
    <Reveal as={as} className="stat" delay={delay}>
      <p className="stat__value">
        {value}
        <RefMarks refs={refs} />
      </p>
      <p className="stat__label">{label}</p>
    </Reveal>
  );
}
