import React from "react";
import { NavLink } from "react-router-dom";

type NavItem = {
  label: string;
  to: string;
  icon: React.ReactNode;
  badge?: string;
};

const iconClass = "h-5 w-5 text-neutral-500";

const itemsTop: NavItem[] = [
  {
    label: "Funpay Statistics",
    to: "/dashboard",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 20c1.5-4 5-6 8-6s6.5 2 8 6" />
      </svg>
    ),
  },
  {
    label: "Dashboard",
    to: "/dashboard",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M3 10.5L12 3l9 7.5v9a1.5 1.5 0 0 1-1.5 1.5H4.5A1.5 1.5 0 0 1 3 19.5z" />
      </svg>
    ),
  },
  {
    label: "Active Rentals",
    to: "/rentals",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v5l3 2" />
      </svg>
    ),
  },
  {
    label: "Orders History",
    to: "/orders",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="5" y="4" width="14" height="16" rx="2" />
        <path d="M8 2v4M16 2v4M8 10h8M8 14h8" />
      </svg>
    ),
  },
  {
    label: "Tickets (FunPay)",
    to: "/tickets",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M4 7h16v4a2 2 0 1 1 0 4v4H4v-4a2 2 0 1 1 0-4z" />
      </svg>
    ),
  },
  {
    label: "Blacklist",
    to: "/blacklist",
    badge: "3",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="8" />
        <path d="M8 8l8 8" />
      </svg>
    ),
  },
  {
    label: "Inventory",
    to: "/inventory",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <ellipse cx="12" cy="6" rx="7" ry="3" />
        <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
        <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
      </svg>
    ),
  },
  {
    label: "Lots",
    to: "/lots",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <ellipse cx="12" cy="6" rx="7" ry="3" />
        <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" />
      </svg>
    ),
  },
  {
    label: "Chats",
    to: "/chats",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M4 6h16v9a2 2 0 0 1-2 2H9l-5 4V6a2 2 0 0 1 2-2z" />
      </svg>
    ),
  },
  {
    label: "Add Account",
    to: "/add-account",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="4" y="5" width="16" height="14" rx="2" />
        <path d="M12 9v6M9 12h6" />
      </svg>
    ),
  },
  {
    label: "Automations",
    to: "/automations",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
];

const itemsBottom: NavItem[] = [
  {
    label: "Notifications",
    to: "/notifications",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M6 9a6 6 0 1 1 12 0v4l2 2H4l2-2z" />
        <path d="M9.5 19a2.5 2.5 0 0 0 5 0" />
      </svg>
    ),
  },
  {
    label: "Settings",
    to: "/settings",
    icon: (
      <svg viewBox="0 0 24 24" className={iconClass} fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="3" />
        <path d="M19 12a7 7 0 0 0-.1-1l2-1.2-2-3.4-2.3.7a7 7 0 0 0-1.7-1L12.8 2h-3.6l-.2 2.9a7 7 0 0 0-1.7 1l-2.3-.7-2 3.4 2 1.2a7 7 0 0 0 0 2l-2 1.2 2 3.4 2.3-.7a7 7 0 0 0 1.7 1l.2 2.9h3.6l.2-2.9a7 7 0 0 0 1.7-1l2.3.7 2-3.4-2-1.2c.1-.3.1-.7.1-1z" />
      </svg>
    ),
  },
];

const Sidebar: React.FC = () => {
  return (
    <aside className="flex h-screen w-72 flex-col border-r border-neutral-200 bg-white px-6 py-7">
      <div className="text-lg font-semibold text-neutral-900">Funpay Automation</div>

      <nav className="mt-6 flex-1 space-y-2">
        {itemsTop.map((item) => (
          <NavLink
            key={item.label}
            to={item.to}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition",
                isActive
                  ? "bg-neutral-900 text-white shadow-sm"
                  : "text-neutral-700 hover:bg-neutral-100",
              ].join(" ")
            }
          >
            <span className={item.badge ? "text-white" : "text-inherit"}>{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {item.badge ? (
              <span className="flex h-6 min-w-[1.5rem] items-center justify-center rounded-full bg-amber-100 text-xs font-semibold text-amber-700">
                {item.badge}
              </span>
            ) : null}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-2">
        {itemsBottom.map((item) => (
          <NavLink
            key={item.label}
            to={item.to}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition",
                isActive
                  ? "bg-neutral-900 text-white shadow-sm"
                  : "text-neutral-700 hover:bg-neutral-100",
              ].join(" ")
            }
          >
            {item.icon}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </div>
    </aside>
  );
};

export default Sidebar;
