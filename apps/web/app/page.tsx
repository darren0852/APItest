import Link from "next/link";
import AppShell from "./components/AppShell";

const endpoints = [
  { method: "POST", path: "/v1/chat/completions", label: "OpenAI 兼容", color: "var(--accent-2)" },
  { method: "POST", path: "/v1/messages", label: "Anthropic 兼容", color: "var(--cyan)" },
  { method: "POST", path: "/v1/responses", label: "OpenAI Responses", color: "var(--accent-2)" },
];

const features = [
  { title: "四大供应商分组", desc: "Zhipu GLM · Kimi · MiniMax · DeepSeek，价格公开透明。" },
  { title: "多协议统一网关", desc: "OpenAI Chat Completions、Anthropic Messages、OpenAI Responses 三端点全支持。" },
  { title: "缓存感知计费", desc: "缓存读取 / 创建 / 普通输入 / 输出分单价精确计费，不会重复扣。" },
  { title: "余额 + 套餐双轨制", desc: "先预留，请求完成后按实际 Token 结算，账本不可篡改。" },
  { title: "客户 Key 独立管理", desc: "限额、速率、分组、过期时间全部可控。" },
  { title: "供应商路由切换", desc: "改上游模型 ID 或 Key 即刻换供应商，客户计费不变。" },
];

export default function Home() {
  return (
    <AppShell active="/" title="Nova API" subtitle="统一 AI 模型网关 · 四大供应商 · 多协议兼容">
      <div className="grid grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div style={{ marginBottom: 14 }}><span className="badge badge-info">四协议统一网关</span></div>
          <h2 className="section-title" style={{ fontSize: 24, lineHeight: 1.35 }}>
            把模型交付能力<br />集中到自己的中转站
          </h2>
          <p className="stat-mini" style={{ margin: "14px 0 18px" }}>
            一个 Base URL 即可接入所有模型，客户用独立 API Key，按 Token 结算。
          </p>
          <div style={{ display: "flex", gap: 10 }}>
            <Link className="button button-primary" href="/login">开始使用</Link>
            <Link className="button button-secondary" href="/models">查看模型</Link>
          </div>
        </div>
        <div className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: 12 }}>
          <div className="stat-label">可用端点</div>
          {endpoints.map((ep) => (
            <div key={ep.path} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", borderRadius: 9, background: "rgba(255,255,255,.03)", border: "1px solid var(--line)" }}>
              <span className="badge badge-accent" style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>{ep.method}</span>
              <div style={{ flex: 1 }}>
                <div className="mono" style={{ color: ep.color, fontSize: 12 }}>{ep.path}</div>
                <div className="stat-fade" style={{ fontSize: 10.5 }}>{ep.label}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-3">
        {features.map((f) => (
          <div className="card" key={f.title} style={{ padding: 18 }}>
            <h3 className="section-title" style={{ fontSize: 13.5, marginBottom: 6 }}>{f.title}</h3>
            <p className="stat-mini" style={{ lineHeight: 1.65 }}>{f.desc}</p>
          </div>
        ))}
      </div>
    </AppShell>
  );
}
