import Link from "next/link";
import AppShell from "./components/AppShell";

export default function Home() {
  return (
    <AppShell active="/" title="Nova API 中转站" subtitle="统一模型接入，透明计费和完整用量控制">
      <div className="grid grid-2">
        <div className="card">
          <div className="badge badge-info">兼容 OpenAI / Anthropic</div>
          <h2 className="section-title" style={{ marginTop: 14, fontSize: 26 }}>把模型交付能力集中在自己的中转站</h2>
          <p className="stat-mini" style={{ lineHeight: 1.7 }}>统一网关、独立客户密钥、钱包或套餐计费、不可变账本，以及模型级价格透明。</p>
          <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
            <Link className="button button-primary" href="/login">登录</Link>
            <Link className="button button-secondary" href="/register">注册</Link>
            <Link className="button button-ghost" href="/models">模型广场 →</Link>
          </div>
        </div>
        <div className="card">
          <h2 className="section-title">调用端点</h2>
          <div className="mono" style={{ display: "block", overflowWrap: "anywhere" }}>POST {`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}`}/v1/chat/completions</div>
          <div className="stat-mini" style={{ marginTop: 12 }}>使用客户 API Key 作为 Bearer Token。系统会自动预留余额并按实际用量结算。</div>
        </div>
      </div>
      <div className="grid grid-3" style={{ marginTop: 16 }}>
        <div className="card"><h3 className="section-title">模型广场</h3><div className="stat-mini">三组公开模型，每组 15 个，包含能力徽章和官方价对比。</div></div>
        <div className="card"><h3 className="section-title">钱包与套餐</h3><div className="stat-mini">先预留余额，请求完成后按实际 Token 用量结算，账本不可篡改。</div></div>
        <div className="card"><h3 className="section-title">管理控制</h3><div className="stat-mini">在同一个后台管理用户、供应商、定价、账本和审计记录。</div></div>
      </div>
    </AppShell>
  );
}
