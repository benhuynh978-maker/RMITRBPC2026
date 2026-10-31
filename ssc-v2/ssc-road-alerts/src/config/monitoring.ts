// Thresholds for putting a road into the attention queue. The litter level follows the server's
// calibrated scale (1/5/10/20 — see server/config.js); drain inlet coverage keeps the 0–100 scale.
export const MONITORING_CONFIG = {
  wasteThreshold: 10,
  floodThreshold: 70,
  pollIntervalMs: 30_000,
};
