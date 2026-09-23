import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { ApiError } from "./lib/api";
import { AuthProvider, useAuth } from "./lib/auth";
import BoardPage from "./pages/BoardPage";
import LoginPage from "./pages/LoginPage";
import ProjectsPage from "./pages/ProjectsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 2,
    },
  },
});

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted center">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="brand">
          Tracker
        </Link>
        <span className="muted">{user?.name}</span>
        <button className="ghost" onClick={logout}>
          Sign out
        </button>
      </header>
      <main>{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <RequireAuth>
                  <Shell>
                    <ProjectsPage />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/projects/:projectId"
              element={
                <RequireAuth>
                  <Shell>
                    <BoardPage />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
