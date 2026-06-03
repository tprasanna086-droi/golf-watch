import axios from 'axios';

const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL,
});

export default client;

export async function fetchLakes(filters = {}) {
  try {
    const response = await client.get('/api/lakes', { params: filters });
    return response.data;
  } catch (error) {
    console.error('Error fetching lakes:', error);
    throw error;
  }
}

export async function fetchLake(id) {
  try {
    const response = await client.get(`/api/lakes/${id}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching lake ${id}:`, error);
    throw error;
  }
}

export async function fetchAlerts(filters = {}) {
  try {
    const response = await client.get('/api/alerts', { params: filters });
    return response.data;
  } catch (error) {
    console.error('Error fetching alerts:', error);
    throw error;
  }
}

export async function fetchActiveAlerts() {
  try {
    const response = await client.get('/api/alerts/active');
    return response.data;
  } catch (error) {
    console.error('Error fetching active alerts:', error);
    throw error;
  }
}

export async function fetchHistory(lakeId, months) {
  try {
    const response = await client.get(`/api/observations/${lakeId}/history`, {
      params: { months }
    });
    return response.data;
  } catch (error) {
    console.error(`Error fetching history for lake ${lakeId}:`, error);
    throw error;
  }
}
