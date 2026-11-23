import Link from "next/link";
import AppShell from "./components/AppShell";

export default function Home() {
  return (
    <AppShell active="/" title="Nova API 中转站" subtitle="统一模型接入，透明计费和完整用量控制">
      <div className="grid grid-2">
        <div className="card">
          <div className="badge badge-info">OpenAI · Anthropic · Responses 兼容</div>
          <h2 className="section-title" style={{ marginTop: 14, fontSize: 26, color: "var(--ink)" }}>把模型交付<br />能力集中到自己的网关</h2>
          <p className="stat-mini" style={{ lineHeight: 1.8, marginTop: 12 }}>统一网关 · 独立客户密钥 · 钱包或套餐计费 · 不可变账本</p>
          <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
            <Link className="button button-primary" href="/login">开始使用</Link>
            <Link className="button button-secondary" href="/models">查看模型</Link>
          </div>
        </div>
        <div className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <div className="metric-label">Base URL</div>
          <div className="mono" style={{ display: "block", overflowWrap: "anywhere", marginTop: 8, fontSize: 13, color: "var(--accent-2)" }}>https://api.vemixapp.com/v1/chat/completions</div>
          <div className="mono" style={{ display: "block", overflowWrap: "anywhere", marginTop: 6, fontSize: 13, color: "var(--cyan)" }}>POST /v1/messages</div>
          <div className="mono" style={{ display: "block", overflowWrap: "anywhere", marginTop: 6, fontSize: 13, color: "var(--accent-2)" }}>POST /v1/responses</div>
          <div className="stat-mini" style={{ marginTop: 16 }}>使用客户 API Key 作为 Bearer Token，系统按实际 Token 用量结算。</div>
        </div>
      </div>
      <div className="grid grid-3" style={{ marginTop: 16 }}>
        <div className="card">
          <h3 className="section-title">模型广场</h3>
          <div className="stat-mini" style={{ marginTop: 8 }}>四大供应商分组，价格公开透明。</div>
        </div>
        <div className="card">
          <h3 className="section-title">钱包与套餐</h3>
          <div className="stat-mini" style={{ marginTop: 8 }}>先预留余额，请求完成后按实际 Token 结算。</div>
        </div>
        <div className="card">
          <h3 className="section-title">管理控制</h3>
          <div className="stat-mini" style={{ marginTop: 8 }}>在同一个后台管理用户、供应商、定价和供应商路由。</div>
        </div>
      </div>
    </AppShell>
  );
}
