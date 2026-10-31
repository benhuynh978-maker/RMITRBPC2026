// FIELD TEST B01 — 24 Oct 2026, school courtyard, phone on a tripod, A3 ArUco marker board (250 mm).
// These are the team's recorded results (single session, one operator, one location, daytime).
// Everything charted on the Evidence section is derived from the arrays below.

export const TEST_META = {
  id: 'B01',
  date: '24 Oct 2026',
  place: 'school courtyard',
  setup: 'phone on a tripod, A3 ArUco marker board (250 mm)',
};

// Seconds per photo, 21 photos (upload + analysis).
export const TIMING_S = [
  12.1, 12.3, 9.9, 11.7, 9.8, 10.9, 10.7, 12.2, 11.7, 9.7, 8.8, 10.7, 10, 10.1, 10.2, 10.1, 9.6, 10, 10.8, 9.7, 12.1,
];
export const TIMING_TARGET_S = 20;

// Camera height estimated from the marker board: (distance to board in m, estimated height in m).
export const HEIGHT_REF_M = 1.9; // tape-measured
export const HEIGHT_POINTS = [
  [1, 1.73], [1, 1.76], [1.5, 1.78], [1.5, 1.82], [2, 1.81], [2, 1.85], [3, 1.78], [3, 1.77],
];
export const HEIGHT_REFUSED_DISTANCES_M = [4, 5];

// Point-object positions in the board frame (metres). Board centred at (0, 0), 0.25 m square.
// Each row: [trueY, trueX, measuredY, measuredX]
export const BOARD_SIDE_M = 0.25;
export const POSITION_ROWS = [
  [0.5, 0, 0.516, -0.047], [0.5, 0, 0.594, -0.036], [1, 0, 1.19, 0.027], [1, 0, 1.216, -0.026],
  [1.5, 0, 1.495, -0.031], [1.5, 0, 1.459, -0.064], [0, 0.5, 0.028, 0.465], [0, 0.5, 0.02, 0.474],
  [0, 1, -0.026, 0.971], [0, 1, -0.024, 0.941], [1.5, 0.5, 1.589, 0.471], [1.5, 0.5, 1.58, 0.468],
  [1.5, -0.5, 1.725, -0.482], [1.5, -0.5, 1.695, -0.445], [0.5, 0, 0.472, -0.067], [0.5, 0, 0.503, -0.056],
  [1, 0, 1.131, -0.071], [1, 0, 1.058, -0.047], [1.5, 0, 1.71, -0.099], [1.5, 0, 1.557, -0.089],
  [0, 0.5, 0.053, 0.469], [0, 0.5, 0.051, 0.469], [0, 1, 0.029, 0.973], [0, 1, 0.032, 0.963],
  [1, 0.5, 1.108, 0.524], [1, 0.5, 1.117, 0.503], [1, -0.5, 1.03, -0.528], [1, -0.5, 1.112, -0.551],
];

// Validation-set detection metrics (Trash/Drain segmentation).
export const DETECTION = { recall: 0.44, precision: 0.638, map50: 0.459 };

// Summary table. "verdict": ok | warn | bad
export const RESULT_ROWS = [
  {
    test: 'Upload and analysis speed',
    result: '21 of 21 photos delivered and analysed. Median 10.2 s per photo (target: under 20 s).',
    verdict: 'ok',
    label: 'Passed',
  },
  {
    test: 'Camera height from the marker',
    result:
      'Board at 1–3 m accepted, at 4–5 m refused (board under 50 px): 12 of 12 decisions correct. Estimated height vs tape-measured 1.90 m: mean error 5.9%, max 8.9%.',
    verdict: 'ok',
    label: 'Passed',
  },
  {
    test: 'Where the litter lands on the map',
    result:
      '28 shots of a point object at 9 known positions: median position error 7.5 cm, max 23.2 cm. 24 of 28 within 0.20 m, 4 within 0.20–0.40 m. A systematic offset of about +7 cm along the board’s +Y axis (we believe object height; not yet confirmed).',
    verdict: 'warn',
    label: 'Passed with bias',
  },
  {
    test: 'Litter area estimate',
    result:
      'Small, non-flat objects were over-estimated by 1.7–2.9× in area. We will retest with larger flat objects.',
    verdict: 'bad',
    label: 'Not passed',
  },
  {
    test: 'Model detection (validation set)',
    result:
      'Recall 0.44, precision 0.638, mAP50 0.459 for Trash/Drain segmentation. The model still misses litter; improving it is our main next step.',
    verdict: 'bad',
    label: 'Needs improvement',
  },
];
