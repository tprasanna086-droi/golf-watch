import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import MapView from './components/MapView';
import LakeDetail from './components/LakeDetail';
import AlertsFeed from './components/AlertsFeed';
import { fetchLakes, fetchActiveAlerts, fetchHistory } from './api/client';
import './App.css';

function App() {
  const [lakes, setLakes] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [selectedLake, setSelectedLake] = useState(null);
  const [lakeHistory, setLakeHistory] = useState([]);
  const [loadingLakes, setLoadingLakes] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadInitialData() {
      try {
        setLoadingLakes(true);
        const [lakesData, alertsData] = await Promise.all([
          fetchLakes(),
          fetchActiveAlerts(),
        ]);
        setLakes(lakesData);
        setAlerts(alertsData);
        setError(null);
      } catch (err) {
        console.error('Failed to load initial data:', err);
        setError('Could not connect to API server. Operating in offline demo mode.');
        // Set some dummy data for previewing UI if API is down
        setLakes([
          { id: 1, name: 'Tsho Rolpa', district: 'Dolakha', basin: 'Koshi', lat: 27.8617, lon: 86.4772, initial_area_ha: 1.54, risk_class: 'critical' },
          { id: 2, name: 'Imja Tsho', district: 'Solukhumbu', basin: 'Koshi', lat: 27.8983, lon: 86.9350, initial_area_ha: 1.01, risk_class: 'critical' },
          { id: 3, name: 'Thulagi', district: 'Manang', basin: 'Gandaki', lat: 28.4878, lon: 84.4653, initial_area_ha: 0.76, risk_class: 'critical' },
          { id: 4, name: 'Tilicho Lake', district: 'Manang', basin: 'Gandaki', lat: 28.6833, lon: 83.8500, initial_area_ha: 4.80, risk_class: 'low' },
        ]);
        setAlerts([
          { id: 1, lake_id: 1, name: 'Tsho Rolpa', lat: 27.8617, lon: 86.4772, alert_level: 'emergency' }
        ]);
      } finally {
        setLoadingLakes(false);
      }
    }

    loadInitialData();
  }, []);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const alertsData = await fetchActiveAlerts();
        setAlerts(alertsData);
      } catch (err) {
        console.error('Failed to poll active alerts:', err);
      }
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  const handleLakeClick = async (lake) => {
    setSelectedLake(lake);
    setLoadingHistory(true);
    try {
      const historyData = await fetchHistory(lake.id, 12);
      setLakeHistory(historyData);
    } catch (err) {
      console.error(`Failed to fetch history for lake ${lake.id}:`, err);
      // Fallback dummy history if API is offline
      setLakeHistory([
        { observed_at: '2025-06-01', area_ha: lake.initial_area_ha * 0.95, ndwi_mean: 0.45, turbidity_index: 0.12 },
        { observed_at: '2025-08-01', area_ha: lake.initial_area_ha * 1.02, ndwi_mean: 0.48, turbidity_index: 0.15 },
        { observed_at: '2025-10-01', area_ha: lake.initial_area_ha * 1.10, ndwi_mean: 0.52, turbidity_index: 0.18 },
        { observed_at: '2025-12-01', area_ha: lake.initial_area_ha * 1.25, ndwi_mean: 0.56, turbidity_index: 0.22 },
      ]);
    } finally {
      setLoadingHistory(false);
    }
  };

  return (
    <div className="app">
      {error && (
        <div className="offline-banner">
          <span>⚠️ {error}</span>
        </div>
      )}
      
      <Sidebar
        lakes={lakes}
        selectedLake={selectedLake}
        onLakeClick={handleLakeClick}
        loading={loadingLakes}
      />

      <MapView
        lakes={lakes}
        alerts={alerts}
        onLakeClick={handleLakeClick}
      />

      {selectedLake ? (
        <LakeDetail
          lake={selectedLake}
          history={lakeHistory}
          loading={loadingHistory}
        />
      ) : (
        <div className="detail-panel">
          <AlertsFeed alerts={alerts} onLakeClick={handleLakeClick} />
        </div>
      )}
    </div>
  );
}

export default App;
