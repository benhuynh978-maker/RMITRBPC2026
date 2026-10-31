# CleanSight — project website

Two-page, bilingual (Vietnamese / English) website that introduces **CleanSight**: street-litter monitoring with fixed cameras and computer vision, mapped to where crews should clear first.

Built with React 19, Vite and React Router, plain CSS. Static site: no backend, no analytics, no cookies, no external fonts or requests at runtime. The "Try the AI" page shows three **pre-computed** sample results (the model was run offline on each sample photo; nothing is analysed live). Uploading your own photo is not built yet: that control is disabled and marked *Coming soon*.

## Pages

| Route | Page |
|---|---|
| `/` | Home: problem, solution, how it works, deployment, what is new, SDG 11, references, contact |
| `/thu-ai` | Try the AI (3 pre-computed samples; upload coming soon) |

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

## Sample results (Try the AI)

Every number, outlined photo and note on `/thu-ai` comes from `src/data/samples.json` and `public/img/samples/`, generated offline by `research/cleansight_samples/make_samples.py` (model `baseline_v1_rev2`, single-photo method, no drain zone). Do not edit `samples.json` by hand: change the source photos and re-run the script. The text notes about each sample (what the model got wrong) are in `src/i18n/*.js` under `tryAi.samples` and must be re-checked against the annotated image whenever a sample is regenerated. Sample photos must be the team's own, with no people, vehicle plates or logos.

## Source layout

```
src/
  App.jsx            router, layout, legacy redirects
  main.jsx           fonts + CSS
  i18n/              dictionaries and provider
  components/        Nav, Footer, Section, cards, diagram, references, scroll manager…
  pages/             Home, TryAI, NotFound
  lib/               contact email, references, nav items
  data/              samples.json (generated, see above)
  styles/            tokens, base, components, pages
public/              favicon, hero photo, img/samples, _headers, _redirects
```
