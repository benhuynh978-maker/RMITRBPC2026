# CleanSight — project website

Two-page, bilingual (Vietnamese / English) website that introduces **CleanSight**: street-litter monitoring with fixed cameras and computer vision, mapped to where crews should clear first.

Built with React 19, Vite and React Router, plain CSS. Static site: no backend, no analytics, no cookies, no external fonts or requests at runtime. The "Try the AI" page shows three **pre-computed** sample results (the model was run offline on each sample photo) and, during the live-demo window, lets a visitor upload their own photo to a small service run on the team's laptop (see *Live demo* below). The one external request the site can make is to that service; nothing else.

## Pages

| Route | Page |
|---|---|
| `/` | Home: problem, solution, how it works, deployment, what is new, SDG 11, references, contact |
| `/thu-ai` | Try the AI (3 pre-computed samples + live upload when the demo is open) |

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

The repository root has a `netlify.toml` that sets `base = "cleansight-site-v2"`, and this folder's `netlify.toml` sets the build command (`npm run build`), the publish directory (`dist`, relative to the base), Node 22 and the single-page-app fallback. Security headers and a strict CSP live in `public/_headers`.

**Git-connected site** (Add new site → Import an existing project → GitHub → this repository):

| Setting | Value |
|---|---|
| Branch to deploy (production branch) | `claude/brave-mendel-db9h6k` (**not** `master`: it holds the old site) |
| Base directory, build command, publish directory | leave the detected values; they come from the two `netlify.toml` files |
| Environment variables | none needed |

Every push to the production branch is published to the public site **automatically**. To review before anything goes live, turn on *Deploys → Stop auto publishing*: each push is still built, and you publish it with one click.

**Without Git:** `npm ci && npm run build`, then drag the `dist/` folder onto Netlify (Add new site → Deploy manually).

After the first deploy: open `/thu-ai` directly (the SPA fallback must serve it), switch VI/EN, click the three samples, and check that the status chip reads *offline* while the laptop demo is closed.

`index.html` contains `<meta name="robots" content="noindex">`, so search engines will not list the site; people with the link can still open it. Remove that tag to allow indexing.

## Text and languages

All visible text is in `src/i18n/vi.js` and `src/i18n/en.js` (identical keys). The default language follows the browser; the **VI | EN** toggle saves the choice in `localStorage` (`cleansight.lang`). The slogan is a single key, `brand.slogan`.

## Live demo (upload your own photo)

Service: `research/cleansight_demo_api/` (see its README for how to open and close it each day). The page asks `GET /api/health` on load and every 30 s; when it answers the status chip says *online* and the upload box is enabled, otherwise it says *offline* and only the samples work. The photo is shrunk to 1600 px and re-encoded in the browser (this drops EXIF/location), sent as raw `image/jpeg`, analysed in the service's memory and never saved.

Where the page looks for the service: `DEMO_API_URL` in `src/lib/config.js` (default: the team laptop's Tailscale Funnel address, port 443). Override at build time with `VITE_DEMO_API_URL=https://...`; an **empty** value turns the live demo off and makes no network request. The same origin is allowed in `public/_headers` (`connect-src`): change both together, otherwise the browser blocks the request. The service in turn only accepts calls from the site's own address (`-Origin` of `open_demo.ps1`).

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
