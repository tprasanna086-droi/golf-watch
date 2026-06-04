import { useCallback, useEffect, useState } from 'react';
import {
  fetchLake,
  fetchLakeAlerts,
  fetchLakeObservations,
} from '../api/lakes';
import { getLakeById, MOCK_LAKES } from '../data/mockLakes';
import { MOCK_ALERTS, MOCK_OBSERVATIONS } from '../data/mockLakeDetail';
import { normalizeLake } from '../utils/lakeUtils';

export function useLake(id) {
  const [lake, setLake] = useState(null);
  const [observations, setObservations] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [usingMock, setUsingMock] = useState(false);

  const load = useCallback(async () => {
    if (!id) {
      setLake(null);
      setObservations([]);
      setAlerts([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [lakeData, obsData, alertsData] = await Promise.all([
        fetchLake(id),
        fetchLakeObservations(id, 24),
        fetchLakeAlerts(id),
      ]);

      setLake(normalizeLake(lakeData));
      setObservations(Array.isArray(obsData) ? obsData : []);
      setAlerts(Array.isArray(alertsData) ? alertsData : []);
      setUsingMock(false);
    } catch (err) {
      console.warn('Using mock data — lake API unavailable:', err);
      const mockLake = getLakeById(id) ?? MOCK_LAKES[0];
      setLake(mockLake);
      setObservations(MOCK_OBSERVATIONS);
      setAlerts(MOCK_ALERTS);
      setUsingMock(true);
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  return {
    lake,
    observations,
    alerts,
    loading,
    error,
    usingMock,
    refetch: load,
  };
}
