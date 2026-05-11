import { useState, useEffect } from "react";
import api from "../lib/api";

export function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .get("/api/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => {
        localStorage.clear();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const { data } = await api.post("/api/auth/login", { email, password });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    const me = await api.get("/api/auth/me");
    setUser(me.data);
    return me.data;
  }

  async function signup(email, password, full_name) {
    const { data } = await api.post("/api/auth/signup", { email, password, full_name });
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    const me = await api.get("/api/auth/me");
    setUser(me.data);
    return me.data;
  }

  function logout() {
    localStorage.clear();
    setUser(null);
  }

  return { user, loading, login, signup, logout };
}
