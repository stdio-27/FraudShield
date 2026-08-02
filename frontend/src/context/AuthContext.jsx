import { createContext, useContext, useState, useEffect } from "react";
import api from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // const [token, setToken] = useState(() => localStorage.getItem('fraudshield_token'));
  // const [isAuthenticated, setIsAuthenticated] = useState(!!token);
  const [token, setToken] = useState(() =>
    localStorage.getItem("fraudshield_token"),
  );
  const isAuthenticated = !!token;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // useEffect(() => {
  //   setIsAuthenticated(!!token);
  // }, [token]);

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
      localStorage.setItem("fraudshield_token", accessToken);
      setToken(accessToken);
      return true;
    } catch (err) {
      const message = err.response?.data?.detail || "Authentication failed";
      setError(message);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("fraudshield_token");
    setToken(null);
  };

  return (
    <AuthContext.Provider
      value={{ token, isAuthenticated, loading, error, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
