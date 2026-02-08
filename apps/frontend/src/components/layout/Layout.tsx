import React, { useState } from "react";
import { motion } from "framer-motion";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { AuthResponse } from "../../services/api";
import { WorkspaceProvider } from "../../context/WorkspaceContext";
import { useI18n } from "../../i18n/useI18n";
import type { TranslationKey } from "../../i18n/translations";

type LayoutProps = {
  user: AuthResponse;
  onLogout: () => Promise<void>;
};

const titles: Record<string, TranslationKey> = {
  "/dashboard": "title.dashboard",
  "/bonus": "title.bonus",
  "/funpay-stats": "title.funpayStats",
  "/rentals": "title.rentals",
  "/orders": "title.orders",
  "/tickets": "title.tickets",
  "/blacklist": "title.blacklist",
  "/low-priority": "title.lowPriority",
  "/inventory": "title.inventory",
  "/lots": "title.lots",
  "/chats": "title.chats",
  "/add-account": "title.addAccount",
  "/automations": "title.automations",
  "/notifications": "title.notifications",
  "/documentation": "title.documentation",
  "/plugins": "title.plugins",
  "/steam-status": "title.steamStatus",
  "/settings": "title.settings",
};

const Layout: React.FC<LayoutProps> = ({ user, onLogout }) => {
  const location = useLocation();
  const { t } = useI18n();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const titleKey =
    titles[location.pathname] ||
    (location.pathname.startsWith("/chats") ? "title.chats" : "title.dashboard");
  const title = t(titleKey);
  const initial = user.username?.[0]?.toUpperCase() || "U";
  const hideWorkspaceControls =
    location.pathname === "/inventory" ||
    location.pathname === "/blacklist" ||
    location.pathname === "/documentation" ||
    location.pathname === "/plugins";
  const isChatRoute = location.pathname.startsWith("/chats");


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
          <main
            className={`flex-1 min-h-0 px-4 py-6 sm:px-6 lg:px-8 ${
              isChatRoute ? "overflow-hidden" : "overflow-y-auto"
            }`}
          >
            <motion.div
              initial={false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              className={`min-h-0 ${isChatRoute ? "h-full" : "min-h-[40vh]"}`}
            >
              <Outlet />
            </motion.div>
          </main>
        </div>
      </div>
    </WorkspaceProvider>
  );
};

export default Layout;
