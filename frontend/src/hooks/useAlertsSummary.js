import { useCallback, useEffect, useState } from 'react';
import { fetchAlertsSummary } from '../api/alerts';

const FALLBACK_SUMMARY = {
  total_unresolved: 3,
  by_severity: { watch: 1, warning: 1, emergency: 1 },
};

export function useAlertsSummary() {
  const [summary, setSummary] = useState(FALLBACK_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await fetchAlertsSummary();
      setSummary(data);
    } catch (err) {
      console.warn('Using mock alerts summary — API unavailable:', err);
      setSummary(FALLBACK_SUMMARY);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { summary, loading, error, refetch: load };
}
