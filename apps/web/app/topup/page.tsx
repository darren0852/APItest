"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "../components/AppShell";

export default function Topup() {
  const [amount, setAmount] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const amounts = [10, 20, 50, 100, 200];
  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const submit = async (value: number) => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setLoading(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${API}/billing/topups`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ amount: value }),
      });
      const data = await response.json();
      if (response.ok) {
        setMessage(`充值成功 · 新余额 RM ${data.balance}`);
        setTimeout(() => router.push("/dashboard"), 1200);
      } else setError(data.detail || "充值失败");
    } catch { setError("服务器错误"); } finally { setLoading(false); }
  };

  return (
    <AppShell active="/topup" title="钱包充值" subtitle="为钱包计费请求增加余额">
      <div className="grid grid-2" style={{ maxWidth: 900 }}>
        <div className="card">
          <div className="section-title">快捷金额</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            {amounts.map((value) => (
              <button key={value} className="button button-secondary" style={{ minHeight: 54, minWidth: 110 }} disabled={loading} onClick={() => submit(value)}>RM {value}</button>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="section-title">自定义金额</div>
          <div style={{ display: "flex", gap: 10 }}>
            <input className="input" type="number" min="1" value={amount} placeholder="RM" onChange={(event) => setAmount(event.target.value)} />
            <button className="button button-primary" disabled={loading || !amount} onClick={() => submit(Number(amount))}>立即充值</button>
          </div>
          {error && <div className="notice notice-danger" style={{ marginTop: 14 }}>{error}</div>}
          {message && <div className="notice notice-success" style={{ marginTop: 14 }}>{message}</div>}
        </div>
      </div>
    </AppShell>
  );
}
