import { useEffect, useRef } from 'react';
import { TileLayer } from 'react-leaflet';
import type { BasemapProvider } from '../../config/basemaps';
export type TileHealth = 'loading' | 'ready' | 'partial' | 'unavailable';
/** A keyed instance scopes counters and callbacks to one provider / retry. */
export function BasemapLayer({ provider, onHealth }: {provider: BasemapProvider; onHealth: (health: TileHealth) => void}) {
  const active = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const counts = useRef({ loaded: 0, errors: 0 });
  const notify = useRef(onHealth); notify.current = onHealth;
  const report = (health: TileHealth) => { if (active.current) notify.current(health); };
  const armTimeout = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => report(counts.current.loaded ? 'partial' : 'unavailable'), 12000);
  };
  useEffect(() => {
    active.current = true;
    armTimeout();
    return () => { active.current = false; clearTimeout(timer.current); };
  }, []);
  return <TileLayer url={provider.url} attribution={provider.attribution} maxNativeZoom={provider.maxNativeZoom} maxZoom={19} eventHandlers={{
    loading: () => { counts.current = {loaded: 0, errors: 0}; report('loading'); armTimeout(); },
    tileload: () => { counts.current.loaded++; },
    tileerror: () => { counts.current.errors++; },
    load: () => {
      clearTimeout(timer.current);
      const { loaded, errors } = counts.current;
      report(errors ? (loaded ? 'partial' : 'unavailable') : 'ready');
    },
  }} />;
}
