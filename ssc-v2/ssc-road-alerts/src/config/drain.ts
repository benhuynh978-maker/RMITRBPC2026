import type { DrainState, DrainStateName } from '../models/drain';

/** Display copy of policy.drainState / readingMaxAgeMs in server/config.js. Change it there, change it here. */
export const DRAIN_POLICY = Object.freeze({
  windowSize: 5,
  minReadings: 3,
  clean: Object.freeze({ enter: 50, exit: 35 }),
  watch: Object.freeze({ enter: 20, exit: 12 }),
  maxAgeMinutes: 15,
});

/** User labels. Code `clean` = "Needs cleaning"; the raw code is never shown. */
export const DRAIN_LABEL: Record<DrainStateName, string> = { clear: 'Low', watch: 'Watch', clean: 'Needs cleaning', unknown: 'Unknown' };

/** Order from worst to least severe, for listing. */
export const DRAIN_ORDER: DrainStateName[] = ['clean', 'watch', 'clear', 'unknown'];

/** Màu chữ/nền (contrast >= 4.5:1). Always paired with text and a distinct icon shape, never colour alone. */
export const DRAIN_COLOR: Record<DrainStateName, { color: string; background: string }> = {
  clear: { color: '#1b6b52', background: '#e8f4ee' },
  watch: { color: '#8a5700', background: '#fff5db' },
  clean: { color: '#b3263a', background: '#fdecef' },
  unknown: { color: '#4d6371', background: '#eef2f4' },
};

export const DRAIN_DESCRIPTION: Record<DrainStateName, string> = {
  clear: 'Drain inlet coverage is low.',
  watch: 'The drain inlet is starting to be covered; keep watching.',
  clean: 'The drain inlet is heavily covered; plan a cleaning.',
  unknown: 'Not enough reliable data to conclude.',
};

export const drainAriaLabel = (state: DrainStateName): string => `Drain status: ${DRAIN_LABEL[state]}`;

/** Decimal number with a dot, at most 1 digit: 37.5 -> "37.5". Does not depend on the environment ICU. */
export const formatPct = (value: number): string => String(Number(value.toFixed(1)));

export function drainThresholdsText(p: typeof DRAIN_POLICY = DRAIN_POLICY): string {
  return `Needs cleaning: entered at ≥ ${p.clean.enter}%, left only when < ${p.clean.exit}%. `
    + `Watch: entered at ≥ ${p.watch.enter}%, left only when < ${p.watch.exit}%. Below that is Low.`;
}

/** Reason when there is no conclusion. Returns '' when ok or no explanation is needed. */
export function drainReasonText(state?: Pick<DrainState, 'reason' | 'window_count' | 'needed'>): string {
  switch (state?.reason) {
    case 'collecting': return `Collecting: ${state.window_count}/${state.needed ?? DRAIN_POLICY.minReadings} valid readings`;
    case 'stale': return `Data is stale (over ${DRAIN_POLICY.maxAgeMinutes} minutes old) or the camera is disconnected`;
    case 'no_data': return 'No readings yet for the current drain zone';
    default: return '';
  }
}
