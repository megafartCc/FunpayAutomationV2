import React from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { AuthResponse } from "../../services/api";
import { WorkspaceProvider } from "../../context/WorkspaceContext";

type LayoutProps = {
  user: AuthResponse;
  onLogout: () => Promise<void>;
};

const titles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/funpay-stats": "Funpay Statistics",
  "/rentals": "Active Rentals",
  "/orders": "Orders History",
  "/tickets": "Tickets (FunPay)",
  "/blacklist": "Blacklist",
  "/low-priority": "Low Priority Accounts",
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
  const title =
    titles[location.pathname] ||
    (location.pathname.startsWith("/chats") ? "Chats" : "Dashboard");
  const initial = user.username?.[0]?.toUpperCase() || "U";

  return (
    <WorkspaceProvider>
      <div className="flex h-screen overflow-hidden bg-neutral-50">
        <Sidebar />
        <div className="flex h-screen min-h-0 flex-1 flex-col overflow-hidden">
          <TopBar title={title} userInitial={initial} onLogout={onLogout} />
          <main className="flex-1 min-h-0 overflow-y-auto px-8 py-6">
            <Outlet />
          </main>
        </div>
      </div>
    </WorkspaceProvider>
  );
};

export default Layout;
