# CleanSight — project website

Two-page, bilingual (Vietnamese / English) website that introduces **CleanSight**: street-litter monitoring with fixed cameras and computer vision, mapped to where crews should clear first.

Built with React 19, Vite and React Router, plain CSS. Static site: no backend, no analytics, no cookies, no external fonts. The only requests it makes outside its own files are the map tiles of the map pages (OpenStreetMap France, under the map attribution) and, for the live-demo features, calls to the team's laptop service. The "Try the AI" page shows three **pre-computed** sample results (the model was run offline on each sample photo) and, during the live-demo window, lets a visitor upload their own photo to a small service run on the team's laptop (see *Live demo* below). The one external request the site can make is to that service; nothing else.

## Pages

| Route | Page |
|---|---|
| `/` | Home: problem, solution, how it works, deployment, what is new, SDG 11, references, contact |
| `/thu-ai` | Try the AI (3 pre-computed samples + live upload when the demo is open) |
| `/hieu-chinh` | Calibration lab: landing page with the two hands-on labs (nav item "Calibration lab") |
| `/hieu-chinh/cong` | Drain lab: outline a drain zone on a sample photo and measure litter coverage (English only) |
| `/ban-do` | Customer map demo: **simulated** city deployment (100 cameras, 6 zones) as a customer would see it: status per camera, priority list, litter outlines in m² on the map (nav item "Map demo"; Vietnamese and English; public) |
| `/lab/board/` | Board lab: ArUco board calibration, then litter drawn on a map (static page in `public/lab/board/`, English only) |
| `/lab/camera/` | Camera lab: **private**, access code required; the team's home camera sends frames that are stored on the team laptop and drawn on a map (static page in `public/lab/camera/`, English only). Not linked from any page or the nav, `noindex` |

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

## Calibration lab (judges' hands-on)

Both labs use the **same live service** and the same availability (online only while the host laptop runs the service; the status chip shows it); the photos are fixed samples held by the service (`research/cleansight_demo_api/lab_samples/`, thumbnails in `public/img/lab/`), judges cannot upload. State (calibration, observations) lives in the service's RAM per browser tab (`X-Lab-Session`) and expires after 30 min idle.

- `/hieu-chinh/cong` is React: `RoiCanvas`, `RoiToolbar` and `roiGeometry.ts` are copied unchanged from the ssc-v2 drain UI; "Measure" posts the polygon to `/api/lab/drain/measure`.
- `/lab/board/` is a copy of the exp02 web test page (`index.html`, `lab.css`, `lab.js`) adapted to CSP (no inline script, Leaflet vendored in `vendor/leaflet`, OpenStreetMap France tiles) and to the sample/session API. **`public/lab/board/lab-config.js` holds the service address and must match `src/lib/config.js` and `connect-src` in `_headers`.** It is a plain page, so it does not follow the VI|EN toggle.
- Photos in `public/img/lab/` show the team's own scenes (a HUTECH bench label and shop logos are visible in the drain photo; the owner accepted this).

## Camera lab (private, home camera)

`/lab/camera/` is a static page (`public/lab/camera/`: `index.html`, `camera.css`, `cam.js`) that reuses the Board lab styles, Leaflet and the service address (`/lab/board/lab-config.js`). It is **not** part of the judges' labs: nothing links to it, it is `noindex`, and the service refuses everything without the access code.

- The access code is checked **on the service** (`POST /api/cam/login`, see `research/cleansight_demo_api/README.md`); the page and the repo contain no code. The page keeps only a short-lived token in `sessionStorage` and sends it in the `X-Cam-Token` header; frames are fetched with that header and shown through `blob:` URLs (hence `blob:` in `img-src` in `public/_headers`).
- Frames are sent by the camera (or a bridge) to the service, which **stores them on the team laptop** (outside the repo) and outlines trash on every new one. The page polls every 10 s, shows the newest frame (or any frame from the history), draws its regions on the map, and can calibrate the camera from a frame that shows the printed ArUco board. Until then a TEMPORARY calibration is used and the page says so.
- Not verified here: a real camera. The page was checked in a browser with frames posted by a script.

## Customer map demo (`/ban-do`, simulated data)

What a customer sees once cameras are installed and set up. **All data is simulated** and the page says so (banner, "Simulated" tag on every camera card, and the page refuses a data file that is not flagged `"simulated": true`). Nothing here is measured, and the cameras are not a real customer's.

- Data: `public/demo-data/city.json` (about 0.5 MB), generated by `research/cleansight_customer_demo/make_demo_data.py` from `camera_sites.json` with a fixed seed. Do not edit it by hand; change the generator and re-run it (see `research/cleansight_customer_demo/README.md`, which also lists what is real and what is simulated, and how camera positions were chosen).
- What is real: the product's own rules are used as they are (median of the last 5 readings within 15 minutes, at least 3 readings, thresholds with hysteresis 20/50 up and 12/35 down; litter and blockage levels) and `test_demo_data.py` checks them step by step against the real backend code. The camera view areas use the same geometry function as the calibration labs.
- Page: `src/pages/CityDemo.jsx`, `src/components/city/` (`CityMap.jsx` with Leaflet, `CameraCard.jsx`), helpers in `src/lib/cityDemo.js`, styles in `src/styles/city.css`, text under `city` in `src/i18n/*.js`. Zoomed out the map shows the six zones as bubbles, zoomed in each camera as a pin (colour, shape and letter for the status), and from zoom 17 the view area, drain zone and litter outlines. Pins can also be reached from the list and the filter tiles (keyboard friendly).
- Map tiles: OpenStreetMap France (allowed in `img-src` of `public/_headers`); Leaflet 1.9.4 is an npm dependency of the site.
- Not shown, and the page says so: per-road alerts, rain, history, and the real-world limits (daytime only, fixed camera, flat ground, model still misses litter).

## Sample results (Try the AI)

Every number, outlined photo and note on `/thu-ai` comes from `src/data/samples.json` and `public/img/samples/`, generated offline by `research/cleansight_samples/make_samples.py` (model `baseline_v1_rev2`, single-photo method, no drain zone). Do not edit `samples.json` by hand: change the source photos and re-run the script. The text notes about each sample (what the model got wrong) are in `src/i18n/*.js` under `tryAi.samples` and must be re-checked against the annotated image whenever a sample is regenerated. Sample photos must be the team's own, with no people, vehicle plates or logos.

## Source layout

```
src/
  App.jsx            router, layout, legacy redirects
  main.jsx           fonts + CSS
  i18n/              dictionaries and provider
  components/        Nav, Footer, Section, cards, diagram, references, scroll manager…
  pages/             Home, TryAI, Lab, DrainLab, CityDemo, NotFound  (/lab/board and /lab/camera are static pages in public/lab/)
  components/city/   CityMap (Leaflet), CameraCard (customer map demo)
  components/lab/    RoiCanvas, RoiToolbar (copied from ssc-v2)
  lib/               contact email, references, nav items
  data/              samples.json (generated, see above)
  styles/            tokens, base, components, pages
public/              favicon, hero photo, img/samples, img/lab, lab/board + lab/camera (static pages), demo-data (simulated city), _headers, _redirects
```
