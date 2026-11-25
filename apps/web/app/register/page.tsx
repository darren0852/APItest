"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const API = "https://api.vemixapp.com";
      const response = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.detail || "注册失败");
        return;
      }
      setMessage("注册成功！正在跳转到登录页…");
      setTimeout(() => router.push("/login"), 1200);
    } catch {
      setError("无法连接服务器");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-panel" style={{ borderRight: "1px solid var(--line)" }}>
        <form className="auth-card" onSubmit={submit}>
          <h2 className="auth-card-title">创建你的账户</h2>
          <p className="auth-card-sub">注册后即可创建密钥访问所有模型。</p>
          {error && <div className="notice notice-danger" style={{ marginBottom: 16 }}>{error}</div>}
          {message && <div className="notice notice-success" style={{ marginBottom: 16 }}>{message}</div>}
          <label className="label">邮箱</label>
          <input className="input" type="email" value={email} placeholder="you@example.com" required onChange={(e) => setEmail(e.target.value)} />
          <label className="label" style={{ marginTop: 16 }}>密码</label>
          <input className="input" type="password" value={password} placeholder="至少 6 位" required onChange={(e) => setPassword(e.target.value)} />
          <button className="button button-primary" style={{ width: "100%", marginTop: 22 }} type="submit" disabled={loading}>
            {loading ? "注册中…" : "创建账户"}
          </button>
          <p className="stat-mini" style={{ marginTop: 18, textAlign: "center" }}>
            已有账号？ <Link href="/login" style={{ color: "var(--accent-2)" }}>直接登录 →</Link>
          </p>
        </form>
      </section>
      <section className="auth-hero">
        <Link href="/" className="brand">
          <div className="brand-mark">AI</div>
          <div>
            <div className="brand-title">Nova API</div>
            <div className="brand-sub">AI Gateway</div>
          </div>
        </Link>
        <span className="badge badge-info">OpenAI · Anthropic · Responses 兼容</span>
        <h1 className="auth-title">一个中转站<br />承载所有 AI 工作负载</h1>
        <p className="auth-desc">四大供应商分组：Zhipu GLM · Kimi · MiniMax · DeepSeek，价格公开透明。</p>
      </section>
    </main>
  );
}
