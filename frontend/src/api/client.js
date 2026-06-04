const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Perform a JSON API request against the GLOF Watch backend.
 *
 * @param {string} path - Path beginning with / (e.g. /api/v1/lakes)
 * @param {RequestInit} [options]
 * @returns {Promise<unknown>}
 */
export async function apiFetch(path, options = {}) {
  const url = `${BASE_URL.replace(/\/$/, '')}${path}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  const text = await response.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const detail =
      typeof body === 'object' && body !== null
        ? body.detail ?? JSON.stringify(body)
        : String(body ?? '');
    throw new Error(
      `API ${response.status} ${response.statusText}: ${detail}`,
    );
  }

  return body;
}

export { BASE_URL };
