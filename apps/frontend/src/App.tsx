import React, { useRef, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import { api } from "./services/api";

type Toast = { message: string; isError?: boolean } | null;

const App: React.FC = () => {
  const [toast, setToast] = useState<Toast>(null);
  const timerRef = useRef<number | null>(null);

  const showToast = (message: string, isError?: boolean) => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    setToast({ message, isError });
    timerRef.current = window.setTimeout(() => setToast(null), 3200);
  };

  const onLogin = async (payload: { username: string; password: string }) => {
    try {
      await api.login(payload);
      showToast("Logged in.");
    } catch (err) {
      const message = (err as { message?: string })?.message || "Login failed";
      showToast(message, true);
      throw err;
    }
  };

  const onRegister = async (payload: { username: string; password: string; golden_key: string }) => {
    try {
      await api.register(payload);
      showToast("Account created.");
    } catch (err) {
      const message = (err as { message?: string })?.message || "Registration failed";
      showToast(message, true);
      throw err;
    }
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={<LoginPage onLogin={onLogin} onRegister={onRegister} onToast={showToast} />}
        />
        <Route path="/" element={<Navigate to="/login" replace />} />
      </Routes>

      {toast ? (
        <div className="toast">
          <span className={toast.isError ? "text-red-200" : "text-amber-200"}>{toast.message}</span>
        </div>
      ) : null}
    </BrowserRouter>
  );
};

export default App;
