"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";

type IconName =
  | "LayoutDashboard"
  | "Radar"
  | "ListTree"
  | "LineChart"
  | "Sparkles"
  | "FlaskConical"
  | "Layers"
  | "NotebookPen"
  | "Clock"
  | "ShieldAlert"
  | "Settings"
  | "Sun"
  | "Moon";

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  switch (name) {
    case "LayoutDashboard":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
      );
    case "Radar":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 12 18 6" />
          <path d="M12 4v2M20 12h-2M12 20v-2M4 12h2" />
        </svg>
      );
    case "ListTree":
      return (
        <svg {...common}>
          <path d="M5 5h6M5 12h10M5 19h6" />
          <path d="M16 8v8M19 5v3M19 16v3" />
        </svg>
      );
    case "LineChart":
      return (
        <svg {...common}>
          <path d="M3 19 9 13l4 4 8-10" />
          <path d="M17 7h4v4" />
        </svg>
      );
    case "Sparkles":
      return (
        <svg {...common}>
          <path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5Z" />
          <path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7Z" />
        </svg>
      );
    case "FlaskConical":
      return (
        <svg {...common}>
          <path d="M9 3h6" />
          <path d="M10 3v6l-5 8a3 3 0 0 0 2.5 4.5h9A3 3 0 0 0 19 17l-5-8V3" />
          <path d="M8 15h8" />
        </svg>
      );
    case "Layers":
      return (
        <svg {...common}>
          <path d="m12 3 9 5-9 5-9-5Z" />
          <path d="m3 12 9 5 9-5" />
          <path d="m3 16 9 5 9-5" />
        </svg>
      );
    case "NotebookPen":
      return (
        <svg {...common}>
          <path d="M5 4h10a2 2 0 0 1 2 2v14H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
          <path d="m14 14 5-5 2 2-5 5-3 1Z" />
        </svg>
      );
    case "Clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </svg>
      );
    case "ShieldAlert":
      return (
        <svg {...common}>
          <path d="M12 3 20 7v5c0 5-3.4 8.5-8 9-4.6-.5-8-4-8-9V7Z" />
          <path d="M12 8v5" />
          <path d="M12 16h.01" />
        </svg>
      );
    case "Settings":
      return (
        <svg {...common}>
          <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
          <circle cx="12" cy="12" r="3" />
          <path d="m5.6 5.6 2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1" />
        </svg>
      );
    case "Sun":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      );
    case "Moon":
      return (
        <svg {...common}>
          <path d="M20 15.2A8.5 8.5 0 0 1 8.8 4 8.5 8.5 0 1 0 20 15.2Z" />
        </svg>
      );
  }
}

const GROUPS: Array<{
  label: string;
  items: Array<{
    label: string;
    href: string;
    icon: IconName;
  }>;
}> = [
  {
    label: "Market Data",
    items: [
      { label: "Overview", href: "/", icon: "LayoutDashboard" },
      { label: "Scanner", href: "/scanner", icon: "Radar" },
      { label: "Option Chain", href: "/option-chain", icon: "ListTree" },
    ],
  },
  {
    label: "Research",
    items: [
      { label: "Analysis", href: "/analysis", icon: "LineChart" },
      { label: "AI Analysis", href: "/ai-analysis", icon: "Sparkles" },
      { label: "Backtest", href: "/backtest", icon: "FlaskConical" },
      { label: "Strategies", href: "/strategies", icon: "Layers" },
    ],
  },
  {
    label: "Trading",
    items: [
      { label: "Paper", href: "/paper", icon: "NotebookPen" },
      { label: "History", href: "/history", icon: "Clock" },
      { label: "Risk", href: "/risk", icon: "ShieldAlert" },
    ],
  },
  {
    label: "System",
    items: [
      { label: "Settings", href: "/settings", icon: "Settings" },
    ],
  },
];

function isMarketOpen(now: Date) {
  const parts = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(now);

  const map = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  const weekday = map.weekday;
  const hour = Number(map.hour);
  const minute = Number(map.minute);

  const weekdayOpen = ["Mon", "Tue", "Wed", "Thu", "Fri"].includes(weekday);
  const totalMinutes = hour * 60 + minute;

  return weekdayOpen && totalMinutes >= 555 && totalMinutes <= 930;
}

function formatIndiaTime(now: Date) {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(now);
}

function applyTheme(theme: "light" | "dark") {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("trading-intelligence-theme", theme);
}

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const stored = localStorage.getItem("trading-intelligence-theme");
    if (stored === "light" || stored === "dark") {
      setTheme(stored);
      applyTheme(stored);
      return;
    }

    const preferred = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches
      ? "dark"
      : "light";

    setTheme(preferred);
    applyTheme(preferred);
  }, []);

  return {
    theme,
    toggle: () => {
      const next = theme === "light" ? "dark" : "light";
      setTheme(next);
      applyTheme(next);
    },
  };
}

function MarketStrip() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const update = () => setNow(new Date());

    update();

    const timer = window.setInterval(update, 1000);

    return () => window.clearInterval(timer);
  }, []);

  const open = useMemo(
    () => (now ? isMarketOpen(now) : false),
    [now]
  );

  const displayTime = now ? formatIndiaTime(now) : "--:--:--";

  return (
    <div className="phase2-marketbar">
      {["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "VIX"].map((symbol) => (
        <div className="phase2-market-item" key={symbol}>
          <div className="phase2-market-symbol">
            {symbol}
          </div>
          <div className="phase2-market-value">
            —
          </div>
        </div>
      ))}

      <div
        className="phase2-market-meta"
        aria-label="Market status"
      >
        <span
          className="phase2-status-dot unknown"
          title="Upstox connection status is not queried by the shared shell"
        />
        <span>UPSTOX · SERVER DATA</span>
        <span className="phase2-market-open">
          {open ? "MARKET OPEN" : "MARKET CLOSED"}
        </span>
        <span>{displayTime} IST</span>
      </div>
    </div>
  );
}

function Sidebar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();

  return (
    <aside className="sidebar">
      <div className="phase2-brand-row">
        <div>
          <div className="brand">
            Trading Intelligence
          </div>
          <div className="tag">
            Indian options research & decision system
          </div>
        </div>

        <div className="phase2-brand-mark" aria-hidden="true">
          TI
        </div>
      </div>

      {GROUPS.map((group, groupIndex) => (
        <div className="phase2-nav-group" key={group.label}>
          {groupIndex > 0 && (
            <div className="phase2-sidebar-divider" />
          )}

          <div className="phase2-nav-label">
            {group.label}
          </div>

          <nav className="nav" aria-label={group.label}>
            {group.items.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname === item.href ||
                    pathname.startsWith(`${item.href}/`);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`phase2-nav-link${active ? " active" : ""}`}
                  aria-current={active ? "page" : undefined}
                >
                  <span className="phase2-nav-icon">
                    <Icon name={item.icon} />
                  </span>
                  <span className="phase2-nav-text">
                    {item.label}
                  </span>
                </Link>
              );
            })}
          </nav>
        </div>
      ))}

      <div
        className="phase2-sidebar-divider"
        style={{ marginTop: "auto" }}
      />

      <button
        type="button"
        className="phase2-theme-button"
        onClick={toggle}
        aria-label={`Switch to ${
          theme === "light" ? "dark" : "light"
        } mode`}
      >
        <span>
          {theme === "light" ? "Light mode" : "Dark mode"}
        </span>
        <span className="phase2-theme-icon">
          <Icon
            name={theme === "light" ? "Sun" : "Moon"}
            size={17}
          />
        </span>
      </button>
    </aside>
  );
}

export function Shell({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="shell">
      <Sidebar />

      <div className="main">
        <MarketStrip />
        {children}
      </div>
    </div>
  );
}

export default Shell;
