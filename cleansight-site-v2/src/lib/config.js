export const CONTACT_EMAIL = 'ngockgmi@gmail.com';

// Live demo service (research/cleansight_demo_api), reached through Tailscale Funnel on port 443.
// Override at build time with VITE_DEMO_API_URL; an empty value turns the live demo off completely
// (no network request is made). The same origin must be listed in public/_headers (connect-src).
export const DEMO_API_URL = (import.meta.env.VITE_DEMO_API_URL ?? 'https://laptop-p8gad5f2.tailc4a76e.ts.net').replace(/\/+$/, '');
export const DEMO_HEALTH_INTERVAL_MS = 30_000;
export const DEMO_HEALTH_TIMEOUT_MS = 5_000;
export const DEMO_REQUEST_TIMEOUT_MS = 60_000;
export const DEMO_MAX_FILE_BYTES = 25 * 1024 * 1024; // refuse before decoding in the browser
export const DEMO_MAX_SIDE_PX = 1600; // photos are shrunk to this before upload (also drops EXIF/location)
