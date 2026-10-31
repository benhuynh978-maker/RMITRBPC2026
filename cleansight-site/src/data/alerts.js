// DEMO DATA — invented, illustrative roads, drains and values. Not real streets, not live.
// Coordinates are generic points near central Ho Chi Minh City (10.78, 106.70).

export const MAP_CENTER = [10.78, 106.7];
export const MAP_ZOOM = 13;

export const LEVELS = ['Low', 'Watch', 'High'];
export const DRAIN_STATES = ['Low', 'Watch', 'Needs cleaning'];

export const LEVEL_ACTIONS = [
  'No extra visit needed. Keep the normal route.',
  'Add this road to today\u2019s route and check the drain inlets along it.',
  'Send a crew here first: clear litter along the kerb and clear the drain inlets before rain.',
];

export const DRAIN_ACTIONS = [
  'No action. The next photo will re-check it.',
  'Inspect at the next pass and clear loose litter.',
  'Clear the inlet as soon as possible, before the next rain.',
];

// baseLevel: 0 Low, 1 Watch, 2 High (before the rain boost)
export const ROADS = [
  { id: 'R1', name: 'Road R1 (example)', baseLevel: 0, photoMin: 4, path: [[10.7580, 106.6780], [10.7646, 106.6978], [10.7712, 106.7176]] },
  { id: 'R2', name: 'Road R2 (example)', baseLevel: 1, photoMin: 6, path: [[10.7712, 106.7176], [10.7844, 106.7264], [10.7998, 106.7308]] },
  { id: 'R3', name: 'Road R3 (example)', baseLevel: 0, photoMin: 9, path: [[10.8020, 106.6780], [10.7932, 106.6934], [10.7822, 106.7066]] },
  { id: 'R4', name: 'Road R4 (example)', labelDir: 'left', baseLevel: 2, photoMin: 3, path: [[10.7822, 106.7066], [10.7778, 106.7165], [10.7712, 106.7176]] },
  { id: 'R5', name: 'Road R5 (example)', baseLevel: 1, photoMin: 12, path: [[10.8130, 106.7000], [10.8042, 106.7132], [10.7998, 106.7308]] },
  { id: 'R6', name: 'Road R6 (example)', baseLevel: 0, photoMin: 7, path: [[10.7536, 106.7220], [10.7624, 106.7352], [10.7778, 106.7440]] },
  { id: 'R7', name: 'Road R7 (example)', baseLevel: 1, photoMin: 5, path: [[10.8240, 106.6736], [10.8152, 106.6890], [10.8130, 106.7000]] },
  { id: 'R8', name: 'Road R8 (example)', baseLevel: 0, photoMin: 15, path: [[10.7470, 106.7000], [10.7558, 106.7099], [10.7646, 106.6978]] },
];

// state: 0 Low, 1 Watch, 2 Needs cleaning
export const DRAINS = [
  { id: 'D1', roadId: 'R4', state: 2, photoMin: 3, pos: [10.7789, 106.7128] },
  { id: 'D2', roadId: 'R2', state: 1, photoMin: 6, pos: [10.7833, 106.7253] },
  { id: 'D3', roadId: 'R3', state: 0, photoMin: 9, pos: [10.7921, 106.6945] },
  { id: 'D4', roadId: 'R5', state: 1, photoMin: 12, pos: [10.8075, 106.7099] },
  { id: 'D5', roadId: 'R1', state: 0, photoMin: 4, pos: [10.7657, 106.6989] },
  { id: 'D6', roadId: 'R7', state: 2, photoMin: 5, pos: [10.8185, 106.6857] },
];
