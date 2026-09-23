import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, ApiError, getToken, setToken } from "./api";
import type { TokenResponse, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(() => getToken() !== null);

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/auth/me")
      .then(setUser)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) setToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const accept = useCallback((res: TokenResponse) => {
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      login: async (email, password) =>
        accept(await api<TokenResponse>("/auth/login", { method: "POST", json: { email, password } })),
      register: async (name, email, password) =>
        accept(
          await api<TokenResponse>("/auth/register", {
            method: "POST",
            json: { name, email, password },
          }),
        ),
      logout: () => {
        setToken(null);
        setUser(null);
      },
    }),
    [user, loading, accept],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
