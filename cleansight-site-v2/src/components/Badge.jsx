/** Small pill label. variant: neutral | teal | accent */
export function Badge({ variant = 'neutral', icon: Icon, children, className = '', ...rest }) {
  return (
    <span className={`badge badge--${variant} ${className}`.trim()} {...rest}>
      {Icon && <Icon size={14} aria-hidden="true" />}
      {children}
    </span>
  );
}
