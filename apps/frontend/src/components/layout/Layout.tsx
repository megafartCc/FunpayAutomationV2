import React, { useState } from "react";
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
  "/plugins": "Plugins",
  "/settings": "Settings",
};

const Layout: React.FC<LayoutProps> = ({ user, onLogout }) => {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const title =
    titles[location.pathname] ||
    (location.pathname.startsWith("/chats") ? "Chats" : "Dashboard");
  const initial = user.username?.[0]?.toUpperCase() || "U";
  const hideWorkspaceControls =
    location.pathname === "/inventory" ||
    location.pathname === "/blacklist" ||
    location.pathname === "/plugins";

  return (
    <WorkspaceProvider>
      <div className="flex h-screen overflow-hidden bg-neutral-50">
        <Sidebar className="hidden lg:flex" />
        {sidebarOpen ? (
          <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setSidebarOpen(false)} />
        ) : null}
        {sidebarOpen ? (
          <Sidebar
            className="fixed left-0 top-0 z-40 w-72 lg:hidden"
            isMobile
            onClose={() => setSidebarOpen(false)}
            onNavigate={() => setSidebarOpen(false)}
          />
        ) : null}
        <div className="flex h-screen min-h-0 flex-1 flex-col overflow-hidden">
          <TopBar
            title={title}
            userInitial={initial}
            onLogout={onLogout}
            hideWorkspaceControls={hideWorkspaceControls}
            onMenuToggle={() => setSidebarOpen((prev) => !prev)}
          />
          <main className="flex-1 min-h-0 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </WorkspaceProvider>
  );
};

export default Layout;
