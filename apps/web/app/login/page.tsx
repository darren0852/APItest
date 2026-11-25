"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { prefetchPublicModels } from "../../lib/public-models";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  useEffect(() => {
    void prefetchPublicModels().catch(() => undefined);
  }, []);

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
        setError(data.detail || "登录失败");
        return;
      }
      localStorage.setItem("token", data.token);
      localStorage.setItem("email", data.email);
      void prefetchPublicModels().catch(() => undefined);
      router.push(data.is_admin ? "/admin" : "/dashboard");
    } catch {
      setError("无法连接服务器");
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
            <div className="brand-sub">AI Gateway</div>
          </div>
        </Link>
        <div>
          <span className="badge badge-info">OpenAI · Anthropic · Responses 兼容</span>
        </div>
        <h1 className="auth-title">一个中转站<br />承载所有 AI 工作负载</h1>
        <p className="auth-desc">
          统一网关 · 独立客户密钥 · 钱包或套餐计费 · 不可变账本 · 四大供应商分组 · 价格公开透明
        </p>
        <div className="grid grid-2" style={{ maxWidth: 420, position: "relative" }}>
          <div className="card" style={{ padding: 16 }}>
            <div className="stat-label">调用端点</div>
            <div className="mono" style={{ marginTop: 8, color: "var(--accent-2)", fontSize: 11.5 }}>POST /v1/chat/completions</div>
            <div className="mono" style={{ color: "var(--cyan)", fontSize: 11.5 }}>POST /v1/messages</div>
            <div className="mono" style={{ color: "var(--accent-2)", fontSize: 11.5 }}>POST /v1/responses</div>
          </div>
          <div className="card" style={{ padding: 16 }}>
            <div className="stat-label">计价货币</div>
            <div className="metric-value" style={{ fontSize: 26 }}>RM</div>
            <div className="stat-fade" style={{ fontSize: 11 }}>马来西亚令吉</div>
          </div>
        </div>
      </section>

      <section className="auth-panel">
        <form className="auth-card" onSubmit={submit}>
          <h2 className="auth-card-title">欢迎回来</h2>
          <p className="auth-card-sub">登录后管理密钥、钱包和模型访问。</p>
          {error && <div className="notice notice-danger" style={{ marginBottom: 16 }}>{error}</div>}
          <label className="label">邮箱</label>
          <input
            className="input" type="email" value={email} placeholder="you@example.com" required
            onChange={(e) => setEmail(e.target.value)}
          />
          <label className="label" style={{ marginTop: 16 }}>密码</label>
          <input
            className="input" type="password" value={password} placeholder="••••••••" required
            onChange={(e) => setPassword(e.target.value)}
          />
          <button className="button button-primary" style={{ width: "100%", marginTop: 22 }} type="submit" disabled={loading}>
            {loading ? "登录中…" : "进入控制台"}
          </button>
          <p className="stat-mini" style={{ marginTop: 18, textAlign: "center" }}>
            还没有账号？ <Link href="/register" style={{ color: "var(--accent-2)" }}>立即注册 →</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
