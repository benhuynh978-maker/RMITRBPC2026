import { Link } from 'react-router-dom';

/**
 * Button or link styled as a button.
 * variant: primary | secondary | ghost | accent ; size: md | sm
 * `to` → router Link, `href` → <a>, otherwise <button>.
 */
export default function Button({
  variant = 'primary',
  size = 'md',
  to,
  href,
  icon: Icon,
  iconAfter: IconAfter,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}) {
  const cls = `btn btn--${variant} btn--${size} ${className}`.trim();
  const inner = (
    <>
      {Icon && <Icon size={18} aria-hidden="true" />}
      <span>{children}</span>
      {IconAfter && <IconAfter size={18} aria-hidden="true" className="btn__after" />}
    </>
  );
  if (to && !disabled) {
    return (
      <Link to={to} className={cls} {...rest}>
        {inner}
      </Link>
    );
  }
  if (href && !disabled) {
    return (
      <a href={href} className={cls} {...rest}>
        {inner}
      </a>
    );
  }
  return (
    <button type={type} className={cls} disabled={disabled} aria-disabled={disabled || undefined} {...rest}>
      {inner}
    </button>
  );
}
