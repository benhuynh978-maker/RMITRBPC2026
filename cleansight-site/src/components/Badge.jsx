const VARIANTS = {
  demo: 'badge-demo',
  placeholder: 'badge-placeholder',
  prototype: 'badge-prototype',
  neutral: 'badge-neutral',
  ok: 'badge-ok',
  warn: 'badge-warn',
  bad: 'badge-bad',
};

export default function Badge({ variant = 'neutral', children, title }) {
  return (
    <span className={`badge ${VARIANTS[variant] ?? VARIANTS.neutral}`} title={title}>
      {children}
    </span>
  );
}
