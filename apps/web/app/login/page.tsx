"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Login() {
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
      const API = "https://api.vemixapp.com";
      const response = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.detail || "Login failed");
        return;
      }
      localStorage.setItem("token", data.token);
      localStorage.setItem("email", data.email);
      router.push(data.is_admin ? "/admin" : "/dashboard");
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
            <div className="brand-sub">AI API 中转站</div>
          </div>
        </Link>
        <div>
          <div className="badge badge-info">兼容 OpenAI · 兼容 Anthropic</div>
          <h1 className="auth-title">一个中转站，承载所有 AI 工作负载</h1>
          <p className="auth-desc">
            追踪钱包余额、管理客户 API Key、监控 Token 用量、对比模型分组，并保持生产流量可控。
          </p>
        </div>
        <div className="grid grid-2">
          <div className="card">
            <div className="metric-label">调用端点</div>
            <div className="mono" style={{ marginTop: 10, display: "block", overflowWrap: "anywhere" }}>
              POST /v1/chat/completions
            </div>
          </div>
          <div className="card">
            <div className="metric-label">计价货币</div>
            <div className="metric-value">RM</div>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <h2 className="auth-card-title">欢迎回来</h2>
          <p className="auth-card-sub">登录后管理密钥、钱包和模型访问。</p>
          <div style={{ marginBottom: 16 }}>
            <label className="label" htmlFor="email">邮箱</label>
            <input id="email" className="input" type="email" value={email} placeholder="you@company.com" required onChange={(event) => setEmail(event.target.value)} />
          </div>
          <div style={{ marginBottom: 18 }}>
            <label className="label" htmlFor="password">密码</label>
            <input id="password" className="input" type="password" value={password} placeholder="Enter password" required onChange={(event) => setPassword(event.target.value)} />
          </div>
          {error && <div className="notice notice-danger" style={{ marginBottom: 15 }}>{error}</div>}
          <button className="button button-primary" style={{ width: "100%", minHeight: 42 }} disabled={loading} type="submit">
            {loading ? "登录中…" : "登录"}
          </button>
          <div style={{ marginTop: 18, textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
            还没有账号？<Link href="/register" style={{ color: "#bed7ff" }}>立即注册</Link>
          </div>
        </form>
      </section>
    </main>
  );
}
