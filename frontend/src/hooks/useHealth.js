import api from '../services/api';
import { usePolling } from './usePolling';

/**
 * Real system status from the unauthenticated GET /health probe.
 * The API answers 503 with a JSON body when the model or database is down;
 * that body is still meaningful, so it is returned instead of thrown.
 * A network failure means the API itself is unreachable.
 */
async function fetchHealth() {
  try {
    const { data } = await api.get('/health');
    return { reachable: true, ...data };
  } catch (err) {
    if (err.response?.data && typeof err.response.data === 'object' && 'status' in err.response.data) {
      return { reachable: true, ...err.response.data };
    }
    return { reachable: false };
  }
}

export function useHealth() {
  return usePolling(fetchHealth, { interval: 30000 });
}
