import axios from 'axios';

// In production (e.g., Vercel), set VITE_API_BASE_URL to the full backend URL.
// In local development, the Vite proxy handles /api -> localhost:8000.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token to every outgoing request automatically
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('fraudshield_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle 401 responses globally — force re-login, EXCEPT for the login endpoint itself
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // If we get a 401, but the request was specifically FOR the login endpoint, 
    // let the component handle it (so it can show the "Incorrect password" error)
    // without doing a full page hard reload.
    const isLoginRequest = error.config && error.config.url && error.config.url.includes('/auth/login');
    
    if (error.response && error.response.status === 401 && !isLoginRequest) {
      localStorage.removeItem('fraudshield_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
