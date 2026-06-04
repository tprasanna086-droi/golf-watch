import { useCallback, useEffect, useState } from 'react';
import { fetchLakes } from '../api/lakes';
import { MOCK_LAKES } from '../data/mockLakes';
import { normalizeLake } from '../utils/lakeUtils';

export function useLakes() {
  const [lakes, setLakes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [usingMock, setUsingMock] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await fetchLakes();
      setLakes(Array.isArray(data) ? data.map(normalizeLake) : []);
      setUsingMock(false);
    } catch (err) {
      console.warn('Using mock data — lakes API unavailable:', err);
      setLakes(MOCK_LAKES);
      setUsingMock(true);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { lakes, loading, error, usingMock, refetch: load };
}
