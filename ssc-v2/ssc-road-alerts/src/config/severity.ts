import type { Severity } from '../models/roadAlert';
export const SEVERITY: Record<Severity, { label: string; color: string; background: string; rank: number; advice: string }> = {
  normal: { label: 'Normal', color: '#218264', background: '#e8f4ee', rank: 0, advice: 'Keep observing while travelling.' },
  low: { label: 'Low', color: '#347dc1', background: '#ebf3fc', rank: 1, advice: 'Watch the road surface condition.' },
  medium: { label: 'Medium', color: '#a76a00', background: '#fff5db', rank: 2, advice: 'Slow down and observe the road section.' },
  high: { label: 'High', color: '#df671b', background: '#fff0e5', rank: 3, advice: 'Take care; consider another route.' },
  critical: { label: 'Critical', color: '#d33c4c', background: '#fdecef', rank: 4, advice: 'Avoid the road section if possible and follow official notices.' },
};
export const SEVERITY_ORDER: Severity[] = ['critical','high','medium','low','normal'];
