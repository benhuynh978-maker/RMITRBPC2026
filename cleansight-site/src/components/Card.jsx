export default function Card({ as: Tag = 'div', className = '', title, badge, children, ...rest }) {
  return (
    <Tag className={`card ${className}`.trim()} {...rest}>
      {(title || badge) && (
        <div className="card-head">
          {title && <h3>{title}</h3>}
          {badge}
        </div>
      )}
      {children}
    </Tag>
  );
}
