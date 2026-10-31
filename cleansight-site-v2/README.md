# CleanSight — project website

Two-page, bilingual (Vietnamese / English) website that introduces **CleanSight**: street-litter monitoring with fixed cameras and computer vision, mapped to where crews should clear first.

Built with React 19, Vite and React Router, plain CSS. Static site: no backend, no analytics, no cookies, no external fonts or requests at runtime. The "Try the AI" page is an interface preview only (controls are disabled and marked *Coming soon*).

## Pages

| Route | Page |
|---|---|
| `/` | Home: problem, solution, how it works, deployment, what is new, SDG 11, references, contact |
| `/thu-ai` | Try the AI (interface preview, coming soon) |

Old paths `/cong-nghe`, `/thu-nghiem` and `/lien-he` redirect to the matching section of the home page.

## Run locally

Requires Node.js 20.19+ or 22.12+ (see `.nvmrc`).

```bash
npm install
npm run dev        # http://localhost:5180
npm run build      # outputs dist/
npm run preview    # http://localhost:4180, serves dist/
```

## Deploy (Netlify)

`netlify.toml` already sets everything: build command `npm run build`, publish directory `dist`, Node 22 and the single-page-app fallback. Connect this repository in Netlify (*Add new site → Import an existing project*) and keep the detected settings. Security headers and a strict CSP live in `public/_headers` (`self` only).

`index.html` contains `<meta name="robots" content="noindex">`, so search engines will not list the site; people with the link can still open it. Remove that tag to allow indexing.

## Text and languages

All visible text is in `src/i18n/vi.js` and `src/i18n/en.js` (identical keys). The default language follows the browser; the **VI | EN** toggle saves the choice in `localStorage` (`cleansight.lang`). The slogan is a single key, `brand.slogan`.

## Source layout

```
src/
  App.jsx            router, layout, legacy redirects
  main.jsx           fonts + CSS
  i18n/              dictionaries and provider
  components/        Nav, Footer, Section, cards, diagram, references, scroll manager…
  pages/             Home, TryAI, NotFound
  lib/               contact email, references, nav items
  styles/            tokens, base, components, pages
public/              favicon, hero photo, _headers, _redirects
```
