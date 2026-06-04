import { apiFetch } from './client.js';

function queryString(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      search.append(key, String(value));
    }
  });
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export function fetchLakes(skip = 0, limit = 50) {
  return apiFetch(`/api/v1/lakes${queryString({ skip, limit })}`);
}

export function fetchLake(id) {
  return apiFetch(`/api/v1/lakes/${id}`);
}

export function fetchLakeObservations(id, limit = 24) {
  return apiFetch(`/api/v1/lakes/${id}/observations${queryString({ limit })}`);
}

export function fetchLakeAlerts(id) {
  return apiFetch(`/api/v1/lakes/${id}/alerts`);
}

export function triggerAnalysis(id) {
  return apiFetch(`/api/v1/lakes/${id}/analyze`, { method: 'POST' });
}
