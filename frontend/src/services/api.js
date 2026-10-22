import axios from "axios";

// In production (e.g., Vercel), set VITE_API_BASE_URL to the full backend URL.
// In local development, fall back to the direct backend URL so requests hit the running FastAPI server.
const api = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, ""),
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach JWT token to every outgoing request automatically
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("fraudshield_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Handle 401 responses globally — force re-login, EXCEPT for the login endpoint itself
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // If we get a 401, but the request was specifically FOR the login endpoint,
    // let the component handle it (so it can show the "Incorrect password" error)
    // without doing a full page hard reload.
    const isLoginRequest =
      error.config &&
      error.config.url &&
      error.config.url.includes("/auth/login");

    if (error.response && error.response.status === 401 && !isLoginRequest) {
      localStorage.removeItem("fraudshield_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

/**
 * Turn any axios error into a message that is safe to render.
 * FastAPI returns `detail` as a string for most errors but as an array of
 * {loc, msg, type} objects for 422 validation errors.
 */
export function getErrorMessage(err, fallback = "Something went wrong") {
  if (!err) return fallback;
  if (!err.response) {
    return err.code === "ERR_NETWORK" || err.message === "Network Error"
      ? "Cannot reach the API. Check that the backend is running and CORS allows this origin."
      : err.message || fallback;
  }
  const { status, data } = err.response;
  const detail = data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => d?.msg).filter(Boolean).join("; ") || fallback;
  }
  if (status === 403) return "You do not have permission to do this.";
  if (status === 429) return "Too many requests. Please wait and try again.";
  if (status >= 500) return "The server hit an error. Please try again shortly.";
  return fallback;
}

export default api;
