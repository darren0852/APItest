"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "../components/AppShell";

export default function Topup() {
  const [amount, setAmount] = useState("");
  const [showUnsupported, setShowUnsupported] = useState(false);
  const router = useRouter();
  const API = "https://api.vemixapp.com";

  return (
    <AppShell active="/topup" title="钱包充值" subtitle="为钱包计费请求增加余额">
      <div style={{ maxWidth: 560 }}>
        <div className="card">
          <div className="section-title">自定义金额</div>
          <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
            <input className="input" type="number" min="1" value={amount} placeholder="RM" onChange={(event) => setAmount(event.target.value)} />
            <button className="button button-primary" disabled={!amount} onClick={() => setShowUnsupported(true)}>立即充值</button>
          </div>
        </div>

        <div className="card" style={{ marginTop: 18 }}>
          <div className="section-title">余额 / 配套兑换</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 18 }}>
            <button className="button button-secondary">余额兑换</button>
            <button className="button button-secondary" onClick={() => router.push("/plans")}>配套兑换</button>
          </div>
        </div>
      </div>

      {showUnsupported && (
        <div className="modal-overlay" onClick={() => setShowUnsupported(false)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()} style={{ maxWidth: 420, textAlign: "center" }}>
            <h2 style={{ marginBottom: 10 }}>暂不支持</h2>
            <p style={{ margin: 0, color: "var(--ink-muted)" }}>自定义金额充值暂未开放，稍后再试。</p>
            <button className="button button-primary" style={{ marginTop: 22, width: "100%" }} onClick={() => setShowUnsupported(false)}>知道了</button>
          </div>
        </div>
      )}
    </AppShell>
  );
}
