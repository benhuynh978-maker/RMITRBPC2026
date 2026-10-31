import { useEffect, useRef } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';

/** Opens any closed <details> around `el` so a #fragment inside it is visible. */
export function revealTarget(el) {
  for (let d = el?.closest('details'); d; d = d.parentElement?.closest('details')) {
    if (!d.open) d.open = true;
  }
}

function scrollToHash(hash, behavior) {
  const id = decodeURIComponent(hash.slice(1));
  const el = id ? document.getElementById(id) : null;
  if (!el) return false;
  revealTarget(el);
  // The sticky nav offset comes from `scroll-margin-top` in base.css.
  el.scrollIntoView({ behavior, block: 'start' });
  return true;
}

/**
 * Scroll handling for client-side navigation:
 * - with a #hash (e.g. /#lien-he from another route, or a direct load of /#lien-he): scroll to that element;
 * - otherwise scroll to the top when the route changes.
 * Runs on every navigation (location.key), so clicking the same section link twice still scrolls.
 */
export default function ScrollManager() {
  const { pathname, hash, key } = useLocation();
  const navType = useNavigationType();
  const first = useRef(true);
  const prevPath = useRef(pathname);

  useEffect(() => {
    const isFirst = first.current;
    const samePage = prevPath.current === pathname;
    first.current = false;
    prevPath.current = pathname;

    if (hash && hash.length > 1) {
      // In-page link clicks (PUSH on the same route) animate (unless reduced motion, via CSS).
      // Arriving from another route, direct loads, back/forward and legacy-route redirects
      // (POP / REPLACE) jump straight to the section.
      const jump = navType !== 'PUSH' || !samePage;
      if (scrollToHash(hash, jump ? 'instant' : 'auto') && jump && document.fonts?.ready) {
        // Web fonts can shift layout after the first paint; settle on the target once they are in.
        document.fonts.ready.then(() => {
          if (window.location.hash === hash) scrollToHash(hash, 'instant');
        });
      }
      return;
    }
    if (!isFirst) window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [pathname, hash, key, navType]);

  return null;
}
