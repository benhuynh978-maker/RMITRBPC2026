/** CleanSight wordmark: small map-pin icon + name. Decorative icon; the text carries the name. */
export default function Logo({ inverted = false }) {
  return (
    <span className={`logo${inverted ? ' logo--inverted' : ''}`}>
      <svg className="logo__icon" viewBox="0 0 64 64" width="30" height="30" aria-hidden="true" focusable="false">
        <rect width="64" height="64" rx="16" fill="currentColor" />
        <path d="M32 9c-9 0-16.3 7.1-16.3 15.9C15.7 36.7 32 55 32 55s16.3-18.3 16.3-30.1C48.3 16.1 41 9 32 9z" fill="#fff" />
        <path d="M32 17.5c-4 5-6.3 8.2-6.3 11.7a6.3 6.3 0 0 0 12.6 0c0-3.5-2.3-6.7-6.3-11.7z" fill="currentColor" />
        <path d="M32 35.5c0-3.8 2.3-7.2 6.7-9-.2 4.6-2.5 7.9-6.7 9z" fill="#E0892B" />
      </svg>
      <span className="logo__text">CleanSight</span>
    </span>
  );
}
