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
  { href: "/dashboard", label: "用户仪表盘", icon: "◈" },
  { href: "/api-keys", label: "API Keys", icon: "⌘" },
  { href: "/models", label: "模型广场", icon: "◇" },
  { href: "/docs", label: "接口文档", icon: "❯" },
];

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
      <aside className="side" style={{ left: sidebarOpen ? 0 : undefined }}>
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
                <span className="side-icon" aria-hidden>{link.icon}</span>
                <span style={{ flex: 1 }}>{link.label}</span>
                {active === link.href && <span style={{ fontSize: 9, opacity: .5 }} aria-hidden>●</span>}
              </Link>
            ))}
          </nav>
        </div>
        <div className="side-footer">
          <div className="stat-label">当前登录</div>
          <div style={{ margin: "6px 0 10px", fontSize: 12.5, wordBreak: "break-all" }}>{email || "用户"}</div>
          <button className="btn btn-secondary" style={{ width: "100%", height: 32, fontSize: 12 }} onClick={logout}>退出登录</button>
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
            <div className="avatar">{initials}</div>
            <div className="avatar-info">
              <div className="avatar-label">{mode === "admin" ? "Admin" : "User"}</div>
              <div className="avatar-email">{email || "—"}</div>
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
