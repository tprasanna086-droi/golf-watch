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

export function fetchAlerts(params = {}) {
  return apiFetch(`/api/v1/alerts${queryString(params)}`);
}

export function fetchAlertsSummary() {
  return apiFetch('/api/v1/alerts/summary');
}

export function resolveAlert(id) {
  return apiFetch(`/api/v1/alerts/${id}/resolve`, { method: 'POST' });
}
