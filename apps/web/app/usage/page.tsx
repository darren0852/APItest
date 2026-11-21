"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "../components/AppShell";

interface UsageRecord { id: number; model: string; input_tokens: number; output_tokens: number; cost: number; created_at: string; }

export default function Usage() {
  const [records, setRecords] = useState<UsageRecord[]>([]);
  const [email, setEmail] = useState("");
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setEmail(localStorage.getItem("email") || "");
    const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${API}/me/usage`, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.status === 401 ? router.push("/login") : response.json())
      .then((data) => Array.isArray(data) && setRecords(data));
  }, []);

  const totalCost = records.reduce((sum, item) => sum + item.cost, 0);
  const totalInput = records.reduce((sum, item) => sum + item.input_tokens, 0);
  const totalOutput = records.reduce((sum, item) => sum + item.output_tokens, 0);

  return (
    <AppShell active="/usage" email={email} title="用量记录" subtitle="每次请求的 Token 消耗和计费明细">
      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        <div className="card"><div className="metric-label">请求数</div><div className="metric-value">{records.length.toLocaleString()}</div></div>
        <div className="card"><div className="metric-label">已计费金额</div><div className="metric-value">RM {totalCost.toFixed(2)}</div></div>
        <div className="card"><div className="metric-label">输入 Token</div><div className="metric-value">{totalInput.toLocaleString()}</div></div>
        <div className="card"><div className="metric-label">输出 Token</div><div className="metric-value">{totalOutput.toLocaleString()}</div></div>
      </div>
      <div className="card">
        <div className="card-title"><h2 className="section-title">请求历史</h2><span className="stat-mini">最近记录</span></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>时间</th><th>模型</th><th>输入</th><th>输出</th><th>费用</th></tr></thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id}>
                  <td>{new Date(record.created_at).toLocaleString()}</td>
                  <td><code className="mono">{record.model}</code></td>
                  <td>{record.input_tokens.toLocaleString()}</td>
                  <td>{record.output_tokens.toLocaleString()}</td>
                  <td>RM {record.cost.toFixed(6)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {records.length === 0 && <div className="empty">还没有用量记录。</div>}
      </div>
    </AppShell>
  );
}
