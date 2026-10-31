import { useEffect, useRef, useState } from 'react';
import type { HandlingRecord, MonitoringAlert } from '../services/monitoringService';

export function useAlertHandling(alerts: MonitoringAlert[], mode: 'api' | 'demo') {
  const storageKey = `ssc:handling:v1:${mode}`;
  const [records, setRecords] = useState<Record<string, HandlingRecord>>({});
  const [storageError, setStorageError] = useState('');
  const [announcement, setAnnouncement] = useState('');
  const seen = useRef(new Set<string>());
  const previousMode = useRef(mode);
  useEffect(() => {
    try {
      const parsed: unknown = JSON.parse(localStorage.getItem(storageKey) ?? '{}');
      const clean: Record<string, HandlingRecord> = {};
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        for (const [key, value] of Object.entries(parsed)) {
          if (!value || typeof value !== 'object') continue;
          if (['acknowledged_at','prepared_at','team','note'].some(field => value[field] !== undefined && typeof value[field] !== 'string')) continue;
          clean[key] = value;
        }
      }
      setRecords(clean); setStorageError('');
    } catch { setRecords({}); setStorageError('Could not read the saved status on this device. Actions are kept for this session only.'); }
  }, [storageKey]);
  useEffect(() => {
    if (previousMode.current !== mode) { seen.current.clear(); previousMode.current = mode; setAnnouncement(''); }
    const fresh = alerts.filter(a => !seen.current.has(a.key));
    // Remove cleared incidents so recurrence can notify again.
    seen.current = new Set(alerts.map(a => a.key));
    if (!alerts.length) setAnnouncement('');
    if (fresh.length) setAnnouncement(`${mode === 'demo' ? 'Simulation: ' : ''}${fresh.length} new or re-prioritised alert(s). ${fresh[0].road.road_name ?? fresh[0].road.road_id}: ${fresh[0].reasons.join('. ')}.`);
  }, [alerts, mode]);
  function update(key: string, patch: HandlingRecord) {
    const next = { ...records, [key]: { ...records[key], ...patch } };
    setRecords(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); setStorageError(''); }
    catch { setStorageError('Could not save on this device. Actions are kept for this session only.'); }
  }
  return { records, update, storageError, announcement, dismiss: () => setAnnouncement('') };
}
