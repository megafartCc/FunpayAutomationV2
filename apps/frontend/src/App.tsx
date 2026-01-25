import React, { useEffect, useRef, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import { api, AuthResponse } from "./services/api";
import Layout from "./components/layout/Layout";
import DashboardPage from "./components/dashboard/DashboardPage";
import FunpayStatsPage from "./components/stats/FunpayStatsPage";
import ActiveRentalsPage from "./components/rentals/ActiveRentalsPage";
import InventoryPage from "./components/inventory/InventoryPage";
import AddAccountPage from "./components/account/AddAccountPage";
import LotsPage from "./components/lots/LotsPage";

type Toast = { message: string; isError?: boolean } | null;

type User = AuthResponse;

const DashboardPlaceholder: React.FC<{ title: string }> = ({ title }) => {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white p-8 text-sm text-neutral-500 shadow-sm">
      <div className="text-lg font-semibold text-neutral-900">{title}</div>
      <p className="mt-2">Protected content will live here.</p>
    </div>
  );
};

const ProtectedRoute: React.FC<{ user: User | null; loading: boolean; children: React.ReactNode }> = ({
  user,
  loading,
  children,
}) => {
  if (loading) {
    return (
      <div className="min-h-screen bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6">
          <div className="h-8 w-40 animate-pulse rounded-full bg-neutral-200" />
          <div className="h-9 w-24 animate-pulse rounded-full bg-neutral-200" />
        </div>
        <div className="mx-auto max-w-5xl px-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="h-28 animate-pulse rounded-2xl border border-neutral-200 bg-neutral-50" />
            <div className="h-28 animate-pulse rounded-2xl border border-neutral-200 bg-neutral-50" />
            <div className="h-28 animate-pulse rounded-2xl border border-neutral-200 bg-neutral-50" />
          </div>
          <div className="mt-6 h-56 animate-pulse rounded-2xl border border-neutral-200 bg-neutral-50" />
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

const AppRoutes: React.FC = () => {
  const [toast, setToast] = useState<Toast>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<number | null>(null);
  const navigate = useNavigate();

  const showToast = (message: string, isError?: boolean) => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    setToast({ message, isError });
    timerRef.current = window.setTimeout(() => setToast(null), 3200);
  };

  useEffect(() => {
    let mounted = true;
    api
      .me()
      .then((me) => {
        if (mounted) setUser(me);
      })
      .catch(() => {
        // not logged in
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const onLogin = async (payload: { username: string; password: string }) => {
    try {
      const me = await api.login(payload);
      setUser(me);
      showToast("Logged in.");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const message = (err as { message?: string })?.message || "Login failed";
      showToast(message, true);
      throw err;
    }
  };

  const onRegister = async (payload: { username: string; password: string; golden_key: string }) => {
    try {
      const me = await api.register(payload);
      setUser(me);
      showToast("Account created.");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      const message = (err as { message?: string })?.message || "Registration failed";
      showToast(message, true);
      throw err;
    }
  };

  const onLogout = async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
      navigate("/login", { replace: true });
    }
  };

  return (
    <>
      <Routes>
        <Route
          path="/login"
          element={
            user && !loading ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <LoginPage onLogin={onLogin} onRegister={onRegister} onToast={showToast} />
            )
          }
        />
        <Route
          path="/"
          element={
            <ProtectedRoute user={user} loading={loading}>
              {user ? <Layout user={user} onLogout={onLogout} /> : null}
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="funpay-stats" element={<FunpayStatsPage />} />
          <Route path="rentals" element={<ActiveRentalsPage onToast={showToast} />} />
          <Route path="orders" element={<DashboardPlaceholder title="Orders History" />} />
          <Route path="tickets" element={<DashboardPlaceholder title="Tickets (FunPay)" />} />
          <Route path="blacklist" element={<DashboardPlaceholder title="Blacklist" />} />
          <Route path="inventory" element={<InventoryPage onToast={showToast} />} />
          <Route path="lots" element={<LotsPage />} />
          <Route path="chats" element={<DashboardPlaceholder title="Chats" />} />
          <Route path="add-account" element={<AddAccountPage />} />
          <Route path="automations" element={<DashboardPlaceholder title="Automations" />} />
          <Route path="notifications" element={<DashboardPlaceholder title="Notifications" />} />
          <Route path="settings" element={<DashboardPlaceholder title="Settings" />} />
        </Route>
      </Routes>
      {toast ? (
        <div className="toast">
          <span className={toast.isError ? "text-red-200" : "text-amber-200"}>{toast.message}</span>
        </div>
      ) : null}
    </>
  );
};

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
};

export default App;
