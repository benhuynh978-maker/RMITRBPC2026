# CleanSight — project-introduction site (design draft)

Static, English-only, single-page site (Vite + React, plain CSS, Leaflet). No backend, no analytics, no external fonts or scripts. The only external request is OpenStreetMap map tiles for the alert-map demo.

> Status: **design review draft.** Demo cards use invented data (badged `DEMO DATA`), photos and team details are placeholders (badged `PLACEHOLDER`). Nothing has been deployed.

## Run and build

```bash
npm install
npm run dev        # dev server (http://localhost:5173)
npm run build      # outputs dist/
npm run preview    # serve dist/ (http://localhost:4173)
```

## Deploy to Netlify

`netlify.toml` already sets build command `npm run build` and publish dir `dist`. `public/_headers` adds security headers (CSP allows only `self` and OSM tiles).

- Drag and drop: run `npm run build`, then drag the `dist/` folder onto Netlify (Sites > Add new site > Deploy manually).
- Or connect the repository and keep the settings from `netlify.toml`.

**Survey form wiring (check at deploy):** the form uses Netlify Forms. Because the page is a React SPA, a hidden static copy of the form lives in `index.html` so Netlify's build detects it (form name `needs-survey`, honeypot `bot-field`). The visible form in `src/sections/Involved.jsx` submits with `fetch` POST to `/` (`application/x-www-form-urlencoded`, includes `form-name`). Field names must stay identical in both places: `org-type, org-name, name, email, area, problems, pilot, consent, bot-field`. On `npm run dev` / `preview` the POST fails by design (no Netlify), so the error state is shown; confirm the success state and that a submission appears in Netlify > Forms after the first deploy. This is a demo form until that check is done.

## Where things live

| What | Where |
| --- | --- |
| Sections (in page order) | `src/sections/*.jsx` (demo cards in `src/sections/demo/`, evidence charts in `src/sections/evidence/`) |
| Reusable components | `src/components/` (`Badge`, `Section`, `Card`, `Nav`) |
| Design tokens (colours, spacing, radius, shadows, type) | `src/styles/tokens.css` |
| Demo data (all invented, header says DEMO DATA) | `src/data/alerts.js` (roads, drains), `src/data/samples.json` (photo frames), `src/lib/smoothing.js` (seeded series + rules), `src/data/team.js` (placeholders) |
| Field-test B01 numbers | `src/data/evidence.js` |
| Map tile URL (single constant) | `src/lib/config.js` (`TILE_URL`) |
| Architecture figure | `public/img/architecture.png` |

## Replace the placeholder photos and polygons

The "Litter on the map" card reads `src/data/samples.json`.

1. Copy a real JPG into `public/img/samples/` (for example `frame1.jpg`).
2. In `samples.json`, set the frame's `"image"` to `"/img/samples/frame1.jpg"` (it is `null` for the placeholder). Set `imageSize` to the photo's pixel size; the frame is drawn at that aspect ratio, and all frames must share one size (or change the code to read a per-frame size).
3. Replace the polygons. Format:
   - `trash[].polygon` and `drain.polygon`: list of `[x, y]` points in **photo pixels** (origin top-left).
   - `trash[].ground`: list of `[x, y]` points in **metres in the marker-board frame**: board centre is `(0, 0)`, `+X` to the right, `+Y` away from the camera along the board's Y axis.
   - `drain.blockagePct`: number, shown as the drain blockage.
   - The "% of the photo" shown for each trash item is computed in the browser from the pixel polygon (shoelace area / image area). No area in m² is shown.
4. Add or remove frames freely (the gallery renders whatever is in `frames`). When real photos are in, remove the "Placeholder – real field photos coming" badge in `src/sections/demo/PhotoExplorer.jsx`.

## Claims and numbers on the page, with sources (for audit)

Source key: **Brief** = the product/design brief given for this site; **B01** = field test B01 results as supplied (24 Oct 2026); **Demo** = invented for the demo, not a fact about the real system; **Computed** = derived in code from the data shown.

| Claim / number | Where on page | Source |
| --- | --- | --- |
| Slogan "Trash with an address"; value sentence (fixed camera, periodic schedule, AI finds litter and blockage, map shows where to collect and which drains first) | Hero | Brief |
| Litter blocks drain inlets, causing local street flooding in rainy-season cities such as Ho Chi Minh City; collection by fixed routes/schedules; crews do not know where or when litter piles up | Problem | Brief |
| Camera: ESP32-S3 + OV5640, 4G modem A7670C, battery + solar; marked "prototype design" | How it works | Brief |
| YOLO26s-seg segments Trash and Drain; drain-blockage index inside a fixed drain zone; temporal smoothing | How it works | Brief |
| Road alert level, drain state, litter zones on the map; Open-Meteo rain data raises the alert one level | How it works, Alert map | Brief |
| Architecture figure (includes the wording "trash zones (m2)" from the original figure) | How it works | Supplied figure `arch_en.png` |
| Roads R1-R8, drains D1-D6, their levels/states, "6 min ago" photo ages, crew actions | Alert map | Demo |
| "Simulate rain" raises every road one level, capped at High | Alert map | Brief (rule), Demo (data) |
| Simulated noisy series (seed 7, 40 photos), counters "state changes raw vs smoothed" | Smoothing | Demo; counters Computed from the series |
| State rules: Low < 20, Watch 20 to <50, Needs cleaning >= 50; hysteresis enter 50 / leave 35, enter 20 / leave 12; median of 5; state shown after >= 3 readings | Smoothing | Brief |
| "76 drains x 20 photos, flip-flops cut from 84 to 2; accuracy improvement not shown" | Smoothing | Brief (offline study) |
| Three sample frames, polygons, blockage %, ground positions | Litter on the map | Demo (placeholder) |
| Board calculator: `S_min = 50 * D / (616 * cos(theta))` for the reference camera (focal about 616 px) and generic `S_min = 50 * D / (f_px * cos(theta))`, `f_px = (width/2) / tan(FOV/2)`; A3 board 0.25 m, A4 backup 0.15 m; "refuse to calibrate if board < 50 px" | Calculator | Brief |
| Upload and analysis: 21/21 photos, median 10.2 s (target < 20 s), 21 per-photo values | Evidence | B01 (median also Computed: 10.2 s) |
| Camera height: 1-3 m accepted, 4-5 m refused (board < 50 px), 12/12 decisions correct; mean error 5.9%, max 8.9% vs 1.90 m tape; 8 plotted points | Evidence | B01 (mean 5.9% / max 8.9% reproduced by Computed) |
| Litter position: 28 shots, 9 positions, median 7.5 cm, max 23.2 cm, 24 within 0.20 m, 4 within 0.20-0.40 m, bias about +7 cm along +Y (believed object height, not confirmed) | Evidence | B01. Computed from the 28 points: max 23.2 cm, 24 / 4 counts and mean +Y shift 7.2 cm match; the **computed median is 7.5 cm** (7.53 cm, mean of the two middle values) while the brief says 7.6 cm (the upper middle value is 7.60 cm). The page now shows the computed 7.5 cm. |
| Litter area: not passed; small non-flat objects over-estimated 1.7-2.9x; retest with larger flat objects | Evidence | B01 |
| Detection: recall 0.44, precision 0.638, mAP50 0.459 (validation set); "main next step" | Evidence, Limits | Brief |
| "Single session, one operator, one location, daytime" | Evidence | Brief |
| Not real-time, not a flood forecast; daytime only; one camera per drain; marker board needed at setup; privacy blurring planned but NOT implemented; area estimate for small objects unreliable | Limits | Brief |
| Roadmap chips (larger area retest, better model, privacy blurring, live try-it page, pilot) | Limits | Brief |
| Audience benefits (pick-up priorities, fewer empty trips, drains before rain, planning evidence, property managers) | Who it's for | Brief (wording expanded; no prices) |
| Team HV Tech, Hung Vuong Gifted High School, 4 members, contact email | Team | Placeholder |
| "Built for RMIT RBPC 2026"; privacy notice (answers used only for this project; no personal photos on the site) | Footer | Brief |

Verdict chips: "Passed", "Passed with bias", "Not passed" come from the brief. The brief did not give a verdict for model detection, so that row uses "Needs improvement" (see report to Tech Lead; change in `src/data/evidence.js` if you prefer another label).

## Accessibility and privacy notes

- Semantic headings, skip link, visible focus styles, alt text/SVG titles, status never conveyed by colour alone (text labels, line styles and marker shapes).
- `prefers-reduced-motion` disables smooth scrolling and transitions.
- Wide charts scroll sideways inside their own box on phones (so text stays legible); the page itself never scrolls horizontally.
- No `localStorage`, cookies, analytics or external fonts.
- Map tiles load from `tile.openstreetmap.org` (attribution shown). Follow the OSM tile usage policy; swap `TILE_URL` in `src/lib/config.js` if traffic grows.
