"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "../components/AppShell";

interface Plan { id: number; name: string; price: number; duration_days: number; daily_request_limit: number | null; total_token_quota: number | null; }

export default function Plans() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const router = useRouter();
  const API = "https://api.vemixapp.com";

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setEmail(localStorage.getItem("email") || "");
    fetch(`${API}/plans`).then((response) => response.json()).then(setPlans);
  }, []);

  const purchase = async (planId: number) => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setError(""); setMessage("");
    const response = await fetch(`${API}/plans/purchase`, {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ plan_id: planId }),
    });
    const data = await response.json();
    if (response.ok) setMessage(`${data.message} · expires ${new Date(data.expires_at).toLocaleDateString()}`);
    else setError(data.detail || "购买失败");
  };

  return (
    <AppShell active="/plans" email={email} title="套餐与计费" subtitle="订阅额度和钱包兜底计费">
      {message && <div className="notice notice-success" style={{ marginBottom: 16 }}>{message}</div>}
      {error && <div className="notice notice-danger" style={{ marginBottom: 16 }}>{error}</div>}
      <div className="grid grid-3">
        {plans.map((plan, index) => (
          <div key={plan.id} className="card" style={{ display: "flex", flexDirection: "column" }}>
            <div className="badge badge-info">{index === 0 ? "入门" : index === 1 ? "推荐" : "规模化"}</div>
            <h2 className="section-title" style={{ marginTop: 12 }}>{plan.name}</h2>
            <div className="metric-value">RM {plan.price}</div>
            <div className="stat-mini">{plan.duration_days} 天</div>
            <div style={{ margin: "18px 0", display: "grid", gap: 9, color: "#c8d2e2", fontSize: 13 }}>
              <div>{plan.daily_request_limit ? `${plan.daily_request_limit} 次/天` : "不限请求数"}</div>
              <div>{plan.total_token_quota ? `${(plan.total_token_quota / 1000).toLocaleString()}K Token` : "不限 Token"}</div>
              <div>套餐不适用时自动走钱包计费</div>
            </div>
            <button className="button button-primary" style={{ marginTop: "auto", width: "100%" }} onClick={() => purchase(plan.id)}>购买套餐</button>
          </div>
        ))}
      </div>
    </AppShell>
  );
}
