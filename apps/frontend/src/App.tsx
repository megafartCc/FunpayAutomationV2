import React, { useRef, useState } from "react";
import LoginPage from "./pages/LoginPage";

type Toast = { message: string; isError?: boolean } | null;

const App: React.FC = () => {
  const [toast, setToast] = useState<Toast>(null);
  const timerRef = useRef<number | null>(null);

  const showToast = (message: string, isError?: boolean) => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    setToast({ message, isError });
    timerRef.current = window.setTimeout(() => setToast(null), 3200);
  };

  const onLogin = async () => {
    showToast("Login is not wired yet.", true);
  };

  const onRegister = async () => {
    showToast("Registration is not wired yet.", true);
  };

  return (
    <div className="min-h-screen">
      <LoginPage onLogin={onLogin} onRegister={onRegister} onToast={showToast} />
      {toast ? (
        <div className="toast">
          <span className={toast.isError ? "text-red-200" : "text-amber-200"}>{toast.message}</span>
        </div>
      ) : null}
    </div>
  );
};

export default App;
