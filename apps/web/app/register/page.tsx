"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.detail || "Registration failed");
        return;
      }
      localStorage.setItem("token", data.token);
      localStorage.setItem("email", data.email);
      router.push("/dashboard");
    } catch {
      setError("Cannot connect to server");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-hero">
        <Link href="/" className="brand">
          <div className="brand-mark">AI</div>
          <div>
            <div className="brand-title">Nova API</div>
            <div className="brand-sub">开发者优先的 AI 中转站</div>
          </div>
        </Link>
        <div>
          <div className="badge badge-success">钱包 + 套餐计费</div>
          <h1 className="auth-title">创建可上生产环境的 API 账号</h1>
          <p className="auth-desc">注册一次，创建独立 API Key，并通过透明用量追踪调用中转站。</p>
        </div>
        <div className="grid grid-2">
          <div className="card"><div className="metric-label">认证</div><div className="metric-value">JWT</div></div>
          <div className="card"><div className="metric-label">账本</div><div className="metric-value">不可变</div></div>
        </div>
      </section>
      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <h2 className="auth-card-title">创建账号</h2>
          <p className="auth-card-sub">先使用钱包计费，需要时再激活套餐。</p>
          <div style={{ marginBottom: 16 }}>
            <label className="label" htmlFor="email">邮箱</label>
            <input id="email" className="input" type="email" value={email} placeholder="you@company.com" required onChange={(event) => setEmail(event.target.value)} />
          </div>
          <div style={{ marginBottom: 18 }}>
            <label className="label" htmlFor="password">密码</label>
            <input id="password" className="input" type="password" value={password} placeholder="Minimum 8 characters" required onChange={(event) => setPassword(event.target.value)} />
          </div>
          {error && <div className="notice notice-danger" style={{ marginBottom: 15 }}>{error}</div>}
          <button className="button button-primary" style={{ width: "100%", minHeight: 42 }} disabled={loading} type="submit">
            {loading ? "创建中…" : "创建账号"}
          </button>
          <div style={{ marginTop: 18, textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
            已经注册？<Link href="/login" style={{ color: "#bed7ff" }}>登录</Link>
          </div>
        </form>
      </section>
    </main>
  );
}
