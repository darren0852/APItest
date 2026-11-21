"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "../components/AppShell";

interface UsageSummary { requests: number; input_tokens: number; output_tokens: number; cost: number; }
interface ApiKey {
  id: number;
  prefix: string;
  name: string;
  group_name: string | null;
  status: string;
  expires_at: string | null;
  created_at: string;
  current_concurrency: number;
  today: UsageSummary;
  month: UsageSummary;
  total: UsageSummary;
  quota_limit: number | null;
  rate_limit: number | null;
}

interface Balance { available: number; reserved: number; currency: string; }
interface Entitlement { id: number; plan_name: string; expires_at: string; remaining_tokens: number | null; daily_requests_used: number; daily_request_limit: number | null; }
interface KeyGroup { id: string; name: string; description: string; }

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const emptyForm = { name: "", group_name: "", quota_limit: "", rate_limit: "", expires_at: "" };

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [balance, setBalance] = useState<Balance | null>(null);
  const [entitlement, setEntitlement] = useState<Entitlement | null>(null);
  const [email, setEmail] = useState("");
  const [newKey, setNewKey] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [modalForm, setModalForm] = useState(emptyForm);
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null);
  const [groupEditorKey, setGroupEditorKey] = useState<number | null>(null);
  const [groupSearch, setGroupSearch] = useState("");
  const [groups, setGroups] = useState<KeyGroup[]>([]);
  const [saving, setSaving] = useState(false);
  const router = useRouter();

  const load = async (token: string) => {
    const keyRes = await fetch(`${API}/me/api-keys`, { headers: { Authorization: `Bearer ${token}` } });
    if (keyRes.status === 401) { router.push("/login"); return; }
    if (keyRes.ok) {
      const keyData = await keyRes.json();
      setKeys(keyData);
    }
    const balanceRes = await fetch(`${API}/me/balance`, { headers: { Authorization: `Bearer ${token}` } });
    if (balanceRes.ok) setBalance(await balanceRes.json());
    const planRes = await fetch(`${API}/me/entitlement`, { headers: { Authorization: `Bearer ${token}` } });
    if (planRes.ok) {
      const plans = await planRes.json();
      setEntitlement(plans.length > 0 ? plans[0] : null);
    }
    const groupRes = await fetch(`${API}/me/model-groups`, { headers: { Authorization: `Bearer ${token}` } });
    if (groupRes.ok) setGroups(await groupRes.json());
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setEmail(localStorage.getItem("email") || "");
    load(token);
  }, []);

  const openCreate = () => { setModal("create"); setModalForm(emptyForm); setEditingKey(null); setError(""); };
  const openEdit = (key: ApiKey) => {
    setModal("edit");
    setEditingKey(key);
    setModalForm({
      name: key.name,
      group_name: key.group_name || "",
      quota_limit: key.quota_limit ? String(key.quota_limit) : "",
      rate_limit: key.rate_limit ? String(key.rate_limit) : "",
      expires_at: key.expires_at ? key.expires_at.slice(0, 16) : "",
    });
    setError("");
  };
  const closeModal = () => { setModal(null); setModalForm(emptyForm); setEditingKey(null); setError(""); setSaving(false); };

  const createKey = async () => {
    if (!modalForm.name || !modalForm.group_name) { setError("请填写名称并选择分组"); return; }
    const token = localStorage.getItem("token");
    if (!token) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`${API}/me/api-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: modalForm.name,
          group_name: modalForm.group_name,
          quota_limit: Number(modalForm.quota_limit || 0),
          rate_limit: Number(modalForm.rate_limit || 0),
          expires_at: modalForm.expires_at || null,
        }),
      });
      const data = await response.json();
      if (response.ok) {
        closeModal();
        await load(token);
      } else setError(data.detail || "创建 Key 失败");
    } catch { setError("服务器错误"); } finally { setSaving(false); }
  };

  const saveKey = async () => {
    if (!editingKey) return;
    const token = localStorage.getItem("token");
    if (!token) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`${API}/me/api-keys/${editingKey.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: modalForm.name,
          group_name: modalForm.group_name || null,
          quota_limit: Number(modalForm.quota_limit || 0),
          rate_limit: Number(modalForm.rate_limit || 0),
          expires_at: modalForm.expires_at || null,
          clear_expires_at: !modalForm.expires_at,
        }),
      });
      const data = await response.json();
      if (response.ok) {
        setMessage("密钥已更新。");
        closeModal();
        await load(token);
      } else setError(data.detail || "更新失败");
    } catch { setError("服务器错误"); } finally { setSaving(false); }
  };

  const chooseGroup = async (keyId: number, groupId: string) => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const current = keys.find((item) => item.id === keyId);
    if (!current) return;
    const response = await fetch(`${API}/me/api-keys/${keyId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ group_name: groupId }),
    });
    const data = await response.json();
    if (response.ok) {
      setMessage("分组已更新。");
      setGroupEditorKey(null);
      setGroupSearch("");
      await load(token);
    } else setError(data.detail || "分组更新失败");
  };

  const toggleStatus = async (key: ApiKey) => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const next = key.status === "active" ? "paused" : "active";
    const response = await fetch(`${API}/me/api-keys/${key.id}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ status: next }),
    });
    const data = await response.json();
    if (response.ok) {
      setMessage(next === "active" ? "密钥已启用。" : "密钥已暂时禁用。");
      await load(token);
    } else setError(data.detail || "状态更新失败");
  };

  const deleteKey = async (id: number) => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const response = await fetch(`${API}/me/api-keys/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
    const data = await response.json();
    if (response.ok) {
      setMessage("密钥已删除。");
      await load(token);
    } else setError(data.detail || "删除失败");
  };

  const activeKeys = keys.filter((key) => key.status === "active");
  const filteredGroups = groups.filter((group) => !groupSearch || group.name.includes(groupSearch) || group.description.includes(groupSearch));

  return (
    <AppShell active="/api-keys" email={email} title="API Keys" subtitle="创建密钥、选择分组、复制密钥和管理调用限制">
      {message && <div className="notice notice-success" style={{ marginBottom: 15 }}>{message}</div>}
      {error && <div className="notice notice-danger" style={{ marginBottom: 15 }}>{error}</div>}

      <div className="grid grid-3" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="metric-label">可用余额</div>
          <div className="metric-value">RM {balance ? balance.available.toFixed(2) : "0.00"}</div>
          <div className="metric-trend">Reserved RM {balance?.reserved.toFixed(2) || "0.00"}</div>
          <Link className="button button-secondary" style={{ marginTop: 14, width: "100%" }} href="/topup">充值</Link>
        </div>
        <div className="card">
          <div className="metric-label">可用密钥</div>
          <div className="metric-value">{activeKeys.length}</div>
          <div className="stat-mini">共 {keys.length} 个 · 可编辑</div>
        </div>
        <div className="card">
          <div className="metric-label">用量</div>
          <div className="metric-value">Live</div>
          <Link className="button button-ghost" style={{ marginTop: 10, padding: 0 }} href="/usage">查看记录 →</Link>
        </div>
      </div>

      <div className="card">
        <div className="card-title">
          <h2 className="section-title">API Keys</h2>
          <button className="button button-primary" onClick={openCreate}>创建密钥</button>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>名称</th><th>API 密钥</th><th>分组</th><th>当前并发</th><th>用量</th><th>过期时间</th><th>状态</th><th>创建时间</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <>
                  <tr key={key.id}>
                    <td><strong>{key.name}</strong></td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <code className="mono">{key.prefix}…</code>
                        <button className="button button-ghost" style={{ padding: 0 }} onClick={() => { navigator.clipboard.writeText(key.prefix); setCopied(true); }}>复制</button>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span className={`badge ${key.group_name ? "badge-info" : "badge-warning"}`}>{groups.find((group) => group.id === key.group_name)?.name || key.group_name || "未选择分组"}</span>
                        <button className="button button-ghost" style={{ padding: 0 }} onClick={() => { setGroupEditorKey(groupEditorKey === key.id ? null : key.id); setGroupSearch(""); }}>选择分组</button>
                      </div>
                    </td>
                    <td><span className="badge badge-info">{key.current_concurrency}</span><span className="stat-mini">上限 {key.rate_limit || 60}/分钟</span></td>
                    <td>
                      <div className="stat-mini">今日 RM {key.today.cost.toFixed(2)}<br />近30天 RM {key.month.cost.toFixed(2)}</div>
                    </td>
                    <td>{key.expires_at ? new Date(key.expires_at).toLocaleString() : "永久有效"}</td>
                    <td><span className={`badge ${key.status === "active" ? "badge-active" : key.status === "paused" ? "badge-warning" : "badge-danger"}`}>{key.status === "active" ? "活跃" : key.status === "paused" ? "暂停" : "已撤销"}</span></td>
                    <td>{new Date(key.created_at).toLocaleString()}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <button className="button button-ghost" onClick={() => toggleStatus(key)}>{key.status === "active" ? "禁用" : "启用"}</button>{" "}
                      <button className="button button-ghost" onClick={() => openEdit(key)}>编辑</button>{" "}
                      <button className="button button-danger" onClick={() => deleteKey(key.id)}>删除</button>
                    </td>
                  </tr>
                  {groupEditorKey === key.id && (
                    <tr key={`group-editor-${key.id}`}>
                      <td colSpan={9}>
                        <div className="card">
                          <input className="input" placeholder="搜索分组…" value={groupSearch} onChange={(event) => setGroupSearch(event.target.value)} />
                          <div className="grid grid-4" style={{ marginTop: 12 }}>
                            {filteredGroups.map((group) => (
                              <button
                                key={group.id}
                                className={key.group_name === group.id ? "button button-primary" : "button button-secondary"}
                                onClick={() => chooseGroup(key.id, group.id)}
                              >
                                {group.name}{key.group_name === group.id ? " ✓" : ""}
                              </button>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
        {keys.length === 0 && <div className="empty">还没有 API Key。充值后点击“创建密钥”。</div>}
      </div>

      {modal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="card-title">
              <strong>{modal === "create" ? "创建密钥" : "编辑密钥"}</strong>
              <button className="button button-ghost" onClick={closeModal}>×</button>
            </div>
            <label className="label">名称</label>
            <input className="input" value={modalForm.name} placeholder="我的 API 密钥" onChange={(event) => setModalForm({ ...modalForm, name: event.target.value })} />
            <label className="label" style={{ marginTop: 15 }}>分组</label>
            <select className="select" value={modalForm.group_name} onChange={(event) => setModalForm({ ...modalForm, group_name: event.target.value })}>
              <option value="">请选择分组</option>
              {groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
            </select>
            <div className="grid grid-4" style={{ marginTop: 15 }}>
              {groups.map((group) => (
                <button
                  key={group.id}
                  className={modalForm.group_name === group.id ? "button button-primary" : "button button-secondary"}
                  onClick={() => setModalForm({ ...modalForm, group_name: group.id })}
                >
                  {group.name}{modalForm.group_name === group.id ? " ✓" : ""}
                </button>
              ))}
            </div>
            <label className="label" style={{ marginTop: 15 }}>额度限制</label>
            <input className="input" type="number" step="0.01" min="0" value={modalForm.quota_limit} placeholder="0 表示不限额" onChange={(event) => setModalForm({ ...modalForm, quota_limit: event.target.value })} />
            <div className="stat-mini" style={{ marginTop: 6 }}>设置此 Key 可消费的最大金额。0 表示不限。</div>
            <label className="label" style={{ marginTop: 15 }}>速率限制</label>
            <input className="input" type="number" min="0" value={modalForm.rate_limit} placeholder="0 表示使用默认 60 次/分钟" onChange={(event) => setModalForm({ ...modalForm, rate_limit: event.target.value })} />
            <label className="label" style={{ marginTop: 15 }}>密钥有效期</label>
            <input className="input" type="datetime-local" value={modalForm.expires_at} onChange={(event) => setModalForm({ ...modalForm, expires_at: event.target.value })} />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button className="button button-secondary" onClick={closeModal}>取消</button>
              <button className="button button-primary" onClick={modal === "create" ? createKey : saveKey} disabled={saving}>{modal === "create" ? "创建" : "保存"}</button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
