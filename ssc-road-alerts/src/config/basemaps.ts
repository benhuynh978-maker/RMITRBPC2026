export interface BasemapProvider { id: string; label: string; url: string; attribution: string; maxNativeZoom: number }
const osmAttribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
export const basemaps: BasemapProvider[] = [
  { id: 'primary', label: import.meta.env.VITE_TILE_NAME || 'OpenStreetMap', url: import.meta.env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: import.meta.env.VITE_TILE_ATTRIBUTION || osmAttribution, maxNativeZoom: 19 },
  { id: 'fallback', label: import.meta.env.VITE_TILE_FALLBACK_NAME || 'OpenTopoMap-R · dự phòng', url: import.meta.env.VITE_TILE_FALLBACK_URL || 'https://tile.openmaps.fr/opentopomap/{z}/{x}/{y}.png', attribution: import.meta.env.VITE_TILE_FALLBACK_ATTRIBUTION || '<a href="https://github.com/sletuffe/OpenTopoMap">&copy; OpenTopoMap-R</a> <a href="https://openmaps.fr/donate">❤️ Donation</a> '+osmAttribution, maxNativeZoom: 17 },
];
