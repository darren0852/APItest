"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { prefetchPublicModels } from "../../lib/public-models";

const userLinks = [
  { href: "/dashboard", label: "仪表盘", icon: "◈" },
  { href: "/api-keys", label: "API Keys", icon: "⌘" },
  { href: "/models", label: "模型广场", icon: "◇" },
  { href: "/usage", label: "用量记录", icon: "◎" },
  { href: "/topup", label: "充值", icon: "＋" },
  { href: "/docs", label: "接口文档", icon: "⌘" },
];

const adminLinks = [
  { href: "/admin", label: "管理后台", icon: "▣" },
  { href: "/dashboard", label: "用户仪表盘", icon: "◈" },
  { href: "/api-keys", label: "API Keys", icon: "⌘" },
  { href: "/models", label: "模型广场", icon: "◇" },
  { href: "/docs", label: "接口文档", icon: "⌘" },
];

export default function AppShell({
  active,
  email,
  title,
  subtitle,
  actions,
  mode = "user",
  children,
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
  const links = mode === "admin" ? adminLinks : userLinks;

  useEffect(() => {
    void prefetchPublicModels().catch(() => undefined);
  }, []);

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    router.push("/login");
  };

  return (
    <div className="app-shell">
      <aside className="side">
        <Link href="/" className="brand">
          <div className="brand-mark">AI</div>
          <div>
            <div className="brand-title">Nova API</div>
          <div className="brand-sub">AI API 中转站</div>
          </div>
        </Link>
        <div>
          <div className="side-label">{mode === "admin" ? "管理" : "工作台"}</div>
          <nav>
            {links.map((link) => (
              <Link key={link.href} href={link.href} className={`side-link${active === link.href ? " active" : ""}`}>
                <span aria-hidden>{link.icon}</span>
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="side-user">
          <div className="metric-label">当前登录</div>
          <div style={{ margin: "5px 0 10px", overflowWrap: "anywhere", fontSize: 13 }}>{email || "用户"}</div>
          <button className="button button-secondary" style={{ width: "100%" }} onClick={logout}>退出登录</button>
        </div>
      </aside>
      <main className="main">
        <div className="page-head">
          <div>
            <h1 className="page-title">{title}</h1>
            {subtitle && <p className="page-sub">{subtitle}</p>}
          </div>
          {actions && <div style={{ display: "flex", gap: 10 }}>{actions}</div>}
        </div>
        {children}
      </main>
    </div>
  );
}
