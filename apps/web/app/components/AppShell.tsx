"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { prefetchPublicModels } from "../../lib/public-models";

const userLinks = [
  { href: "/dashboard", label: "仪表盘", icon: "◈" },
  { href: "/api-keys", label: "API Keys", icon: "⌘" },
  { href: "/models", label: "模型广场", icon: "◇" },
  { href: "/usage", label: "用量记录", icon: "◎" },
  { href: "/topup", label: "充值", icon: "＋" },
  { href: "/docs", label: "接口文档", icon: "❯" },
];

const adminLinks = [
  { href: "/admin", label: "管理后台", icon: "▣" },
];

const sidebarIcons: Record<string, React.ReactNode> = {
  "/admin": (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M4 6h16M4 12h16M4 18h10"/><path d="M17 16.5v3M15.5 18h3"/></svg>),
  "/dashboard": (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/></svg>),
  "/api-keys": (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="8" cy="12" r="4"/><path d="M12 12h8M17 12v3M20 12v2"/></svg>),
  "/models": (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3.5 20 8v8l-8 4.5L4 16V8l8-4.5Z"/><path d="M9.8 13.7a3.5 3.5 0 1 1 4.4 0"/></svg>),
  "/usage": (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>),
  "/topup": (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 8.5v7M8.5 12h7"/></svg>),
  "/docs": (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M13.5 4.5H8A2.5 2.5 0 0 0 5.5 7v10A2.5 2.5 0 0 0 8 19.5h8A2.5 2.5 0 0 0 18.5 17V9.5Z"/><path d="M9 10h6M9 13.5h6"/></svg>),
};

export default function AppShell({
  active, email, title, subtitle, actions, mode = "user", children,
}: {
  active: string;
  email?: string;
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  mode?: "user" | "admin";
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const links = mode === "admin" ? adminLinks : userLinks;

  useEffect(() => {
    void prefetchPublicModels().catch(() => undefined);
    setIsMobile(window.innerWidth <= 768);
  }, []);

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    router.push("/login");
  };

  const initials = (email || "U").slice(0, 2).toUpperCase();

  return (
    <div className="app-shell">
      <aside className={`side${sidebarOpen ? " open" : ""}`}>
        <Link href="/" className="side-logo" onClick={() => setSidebarOpen(false)}>
          <div className="side-logo-mark">AI</div>
          <div>
            <div className="side-logo-name">Nova API</div>
            <div className="side-logo-tag">AI Gateway</div>
          </div>
        </Link>
        <div>
          <div className="side-heading">{mode === "admin" ? "管理" : "工作台"}</div>
          <nav>
            {links.map((link) => (
              <Link key={link.href} href={link.href} className={`side-item${active === link.href ? " active" : ""}`} onClick={() => setSidebarOpen(false)}>
                <span className="side-icon" aria-hidden>{sidebarIcons[link.href] || link.icon}</span>
                <span style={{ flex: 1 }}>{link.label}</span>
                {active === link.href && <span style={{ fontSize: 9, opacity: .5 }} aria-hidden>●</span>}
              </Link>
            ))}
          </nav>
        </div>
      </aside>
      <main className="main">
        <div className="topbar">
          <div>
            <h1 className="topbar-title">{title}</h1>
            {subtitle && <p className="topbar-sub">{subtitle}</p>}
          </div>
          <div className="topbar-user">
            {actions && <div style={{ display: "flex", gap: 10 }}>{actions}</div>}
            <div className="topbar-account">
              <div className="avatar">{initials}</div>
              <div className="avatar-info">
                <div className="avatar-label">当前登录</div>
                <div className="avatar-email">{email || "—"}</div>
              </div>
              <button className="button button-secondary logout-button" onClick={logout} aria-label="退出登录">
                退出登录
              </button>
            </div>
          </div>
        </div>
        {children}
      </main>
      <button
        className="btn btn-secondary"
        style={{ position: "fixed", bottom: 20, left: 20, zIndex: 80, display: isMobile ? "inline-flex" : "none" }}
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        ☰
      </button>
    </div>
  );
}
