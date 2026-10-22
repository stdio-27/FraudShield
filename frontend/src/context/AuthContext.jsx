import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api, { getErrorMessage } from "../services/api";
import { decodeJwt } from "../lib/jwt";

const TOKEN_KEY = "fraudshield_token";
const AuthContext = createContext(null);

function readStoredToken() {
  const stored = localStorage.getItem(TOKEN_KEY);
  if (!stored) return null;
  const claims = decodeJwt(stored);
  // Drop tokens that are unreadable or already expired instead of bouncing off a 401.
  if (!claims || (claims.expiresAt && claims.expiresAt <= Date.now())) {
    localStorage.removeItem(TOKEN_KEY);
    return null;
  }
  return stored;
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(readStoredToken);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const isAuthenticated = !!token;
  const user = useMemo(() => (token ? decodeJwt(token) : null), [token]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }, []);

  // Sign out automatically when the token expires.
  useEffect(() => {
    if (!user?.expiresAt) return undefined;
    const ms = user.expiresAt - Date.now();
    if (ms <= 0) {
      logout();
      return undefined;
    }
    const timer = setTimeout(logout, Math.min(ms, 2 ** 31 - 1));
    return () => clearTimeout(timer);
  }, [user, logout]);

  const login = async (email, password) => {
    setLoading(true);
    setError(null);
    try {
      // FastAPI OAuth2PasswordRequestForm expects form-encoded data
      const formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);

      const response = await api.post("/auth/login", formData, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      const accessToken = response.data.access_token;
      localStorage.setItem(TOKEN_KEY, accessToken);
      setToken(accessToken);
      return true;
    } catch (err) {
      setError(getErrorMessage(err, "Authentication failed"));
      return false;
    } finally {
      setLoading(false);
    }
  };

  // Roles are enforced by the API; this only hides controls it would reject.
  const canModify = user?.role === "admin" || user?.role === "analyst";

  const value = useMemo(
    () => ({ token, user, isAuthenticated, canModify, loading, error, login, logout }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, user, canModify, loading, error, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
