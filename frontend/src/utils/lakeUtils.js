/**
 * Normalize API lake shape for map and list components.
 */
export function normalizeLake(apiLake) {
  return {
    id: apiLake.id,
    name: apiLake.name,
    district: apiLake.district ?? '',
    basin: apiLake.basin ?? '',
    risk_class: apiLake.risk_class ?? 'low',
    area_km2: apiLake.initial_area_km2 ?? 0,
    lat: apiLake.latitude,
    lon: apiLake.longitude,
    latitude: apiLake.latitude,
    longitude: apiLake.longitude,
    initial_area_km2: apiLake.initial_area_km2,
    source: apiLake.source,
    created_at: apiLake.created_at,
  };
}

export function formatMonthLabel(dateStr) {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
}

/**
 * Build recharts series from API observations (chronological).
 */
export function observationsToChartData(observations) {
  if (!observations?.length) return null;

  const sorted = [...observations].sort(
    (a, b) => new Date(a.observed_at) - new Date(b.observed_at),
  );

  return sorted.map((obs) => ({
    month: formatMonthLabel(obs.observed_at),
    area: obs.area_km2 ?? 0,
    ndwi: obs.ndwi_mean ?? 0,
    turbidity: obs.turbidity_index ?? 0,
  }));
}

export function computeGrowthPercent(observations) {
  if (!observations || observations.length < 2) return null;

  const sorted = [...observations].sort(
    (a, b) => new Date(a.observed_at) - new Date(b.observed_at),
  );
  const first = sorted[0]?.area_km2;
  const last = sorted[sorted.length - 1]?.area_km2;
  if (first == null || last == null || first === 0) return null;
  return (((last - first) / first) * 100).toFixed(1);
}

export function formatObservationRow(obs) {
  return {
    id: obs.id,
    date: obs.observed_at,
    area: obs.area_km2 ?? 0,
    ndwi: obs.ndwi_mean ?? 0,
    turbidity: obs.turbidity_index ?? 0,
    cloud: obs.cloud_cover_pct ?? 0,
    tile: obs.sentinel_tile_id ?? '—',
  };
}

export function formatAlertDate(triggeredAt) {
  if (!triggeredAt) return '—';
  return String(triggeredAt).slice(0, 10);
}
