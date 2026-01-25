import React from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { AuthResponse } from "../../services/api";

type LayoutProps = {
  user: AuthResponse;
  onLogout: () => Promise<void>;
};

const titles: Record<string, string> = {
  "/dashboard": "Funpay Statistics",
  "/rentals": "Active Rentals",
  "/orders": "Orders History",
  "/tickets": "Tickets (FunPay)",
  "/blacklist": "Blacklist",
  "/inventory": "Inventory",
  "/lots": "Lots",
  "/chats": "Chats",
  "/add-account": "Add Account",
  "/automations": "Automations",
  "/notifications": "Notifications",
  "/settings": "Settings",
};

const Layout: React.FC<LayoutProps> = ({ user, onLogout }) => {
  const location = useLocation();
  const title = titles[location.pathname] || "Dashboard";
  const initial = user.username?.[0]?.toUpperCase() || "U";

  return (
    <div className="flex min-h-screen bg-neutral-50">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <TopBar title={title} userInitial={initial} onLogout={onLogout} />
        <main className="flex-1 px-8 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
