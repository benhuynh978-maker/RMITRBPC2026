// Primary navigation. `hash` items are sections of the home page (/#id); `path` items are routes.
// Labels come from the `nav.<key>` dictionary keys.
export const NAV_ITEMS = [
  { key: 'problem', hash: 'van-de' },
  { key: 'solution', hash: 'giai-phap' },
  { key: 'how', hash: 'cach-hoat-dong' },
  { key: 'tryAi', path: '/thu-ai' },
  { key: 'lab', path: '/hieu-chinh' },
  { key: 'contact', hash: 'lien-he' },
];

/** Router `to` value for a nav item: home-page sections become `/#id` so they work from any route. */
export const navTarget = (item) => (item.hash ? { pathname: '/', hash: `#${item.hash}` } : item.path);
