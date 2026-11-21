import AppShell from "../components/AppShell";

export default function Docs() {
  return (
    <AppShell active="/docs" title="开发者文档" subtitle="兼容 OpenAI 的中转站接入方式">
      <div className="grid grid-2">
        <div className="card">
          <h2 className="section-title">Base URL 与认证</h2>
          <div className="mono" style={{ display: "block", marginBottom: 12 }}>{`${"https://api.vemixapp.com"}`}/v1</div>
          <pre className="mono" style={{ whiteSpace: "pre-wrap", padding: 14, borderRadius: 12, overflow: "auto" }}>Authorization: Bearer sk-cust-YOUR_KEY_HERE</pre>
        </div>
        <div className="card">
          <h2 className="section-title">Chat Completions 请求示例</h2>
          <pre className="mono" style={{ whiteSpace: "pre-wrap", padding: 14, borderRadius: 12, overflow: "auto" }}>{`curl -X POST ${"https://api.vemixapp.com"}/v1/chat/completions \\
  -H "Authorization: Bearer sk-cust-YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{ "model": "mock-model", "messages": [{"role": "user", "content": "Hello!"}] }'`}</pre>
        </div>
      </div>
      <div className="grid grid-3" style={{ marginTop: 16 }}>
        <div className="card"><h3 className="section-title">认证方式</h3><div className="stat-mini">客户 Key 在 PostgreSQL 中只保存哈希；创建时仅显示一次。</div></div>
        <div className="card"><h3 className="section-title">计费流程</h3><div className="stat-mini">请求先预留余额，返回后按精确 Token 用量结算。</div></div>
        <div className="card"><h3 className="section-title">模型广场</h3><div className="stat-mini">选择线路前先对比分组平台价和官方价。</div></div>
      </div>
    </AppShell>
  );
}
