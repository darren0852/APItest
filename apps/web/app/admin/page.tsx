"use client";

import { useCallback, useEffect, useState } from "react";
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend } from "chart.js";
import { Line } from "react-chartjs-2";
import { useRouter } from "next/navigation";
import AppShell from "../components/AppShell";

interface AdminUser { id: number; email: string; status: string; risk_flag: boolean; created_at: string; balance: number; reserved: number; active_keys: number; total_requests: number; active_plans: number; }
interface UserDetail { user: any; wallet: any; keys: any[]; recent_usage: any[]; recent_ledger: any[]; entitlements: any[]; }
interface Stats { total_users: number; active_users: number; suspended_users: number; flagged_users: number; active_api_keys: number; total_api_requests: number; total_input_tokens: number; total_output_tokens: number; total_cost: number; total_wallet_balance: number; active_plans: number; }
interface Finance { total_topups: number; total_usage_billed: number; total_plan_purchases: number; total_wallet_balance: number; total_reserved: number; total_customer_wallet_balance: number; admin_wallet_balance: number; total_supplier_cost_cny: number; }
interface PriceRow { model: string; group_name: string | null; input_cost: number | null; output_cost: number | null; cache_write_cost: number | null; cache_read_cost: number | null; cost_version: number | null; input_sell: number | null; output_sell: number | null; cache_write_sell: number | null; cache_read_sell: number | null; sell_version: number | null; }
interface PricingGroup { id: number; name: string; model_count: number; key_count: number; }
interface SupplierRoute { id: number; model_name: string; upstream_model: string; endpoint_url: string; api_key_last4: string; }
interface LedgerEntry { id: number; user_id: number; type: string; amount: number; balance_after: number; reference: string; created_at: string; }
interface AuditEntry { id: number; admin: string; action: string; target_type: string | null; target_id: string | null; detail: string | null; created_at: string; }
interface HourlyMultiplierRow { model: string; business_date: string; hourly_multipliers: number[]; }
interface AnalyticsSeries { range: string; buckets: string[]; usage: { input: number[]; output: number[]; cache_write: number[]; cache_read: number[]; }; revenue: number[]; supplier_cost: number[]; profit: number[]; wallet_balance: number[]; groups: { name: string; series: number[] }[]; }

const API = "https://api.vemixapp.com";
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

export default function AdminPage() {
  const [tab, setTab] = useState("stats");
  const [stats, setStats] = useState<Stats | null>(null);
  const [finance, setFinance] = useState<Finance | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [prices, setPrices] = useState<PriceRow[]>([]);
  const [groups, setGroups] = useState<PricingGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState("");
  const [groupName, setGroupName] = useState("");
  const [sortMode, setSortMode] = useState<"group" | "model">("group");
  const [exchangeRate, setExchangeRate] = useState("1");
  const [analyticsRange, setAnalyticsRange] = useState<"today" | "month" | "year">("today");
  const [analyticsSeries, setAnalyticsSeries] = useState<AnalyticsSeries | null>(null);
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [showModelModal, setShowModelModal] = useState(false);
  const [deletePrice, setDeletePrice] = useState<PriceRow | null>(null);
  const [deleteGroup, setDeleteGroup] = useState<PricingGroup | null>(null);
  const [editMultiplier, setEditMultiplier] = useState<HourlyMultiplierRow | null>(null);
  const [multipliers, setMultipliers] = useState<HourlyMultiplierRow[]>([]);
  const [multiplierDate, setMultiplierDate] = useState("");
  const [multiplierDays, setMultiplierDays] = useState<HourlyMultiplierRow[]>([]);
  const [supplierRoutes, setSupplierRoutes] = useState<SupplierRoute[]>([]);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [email, setEmail] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [editPrice, setEditPrice] = useState<PriceRow | null>(null);
  const [adjustUser, setAdjustUser] = useState<number | null>(null);
  const [adjustAmount, setAdjustAmount] = useState("");
  const [adjustReason, setAdjustReason] = useState("");
  const [flagUser, setFlagUser] = useState<number | null>(null);
  const [flagReason, setFlagReason] = useState("");
  const [newRoute, setNewRoute] = useState({ model_name: "", upstream_model: "", endpoint_url: "", api_key: "" });
  const [editRoute, setEditRoute] = useState<SupplierRoute | null>(null);
  const [editRouteKey, setEditRouteKey] = useState("");
  const [newPrice, setNewPrice] = useState({ model: "", input_sell: "", output_sell: "", cache_write: "", cache_read: "" });
  const router = useRouter();

  const get = useCallback(async (path: string) => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return null; }
    const response = await fetch(`${API}/admin/${path}`, { headers: { Authorization: `Bearer ${token}` } });
    if (response.status === 401 || response.status === 403) { setError("需要管理员权限"); return null; }
    if (!response.ok) return null;
    return response.json();
  }, [router]);

  const loadUsers = useCallback(async (query: string, status: string) => {
    let path = "users?";
    if (query) path += `search=${encodeURIComponent(query)}&`;
    if (status) path += `status=${status}`;
    const result = await get(path);
    if (result) setUsers(result);
  }, [get]);

  const loadAll = useCallback(async () => {
    setError("");
    setEmail(localStorage.getItem("email") || "管理员");
    setExchangeRate(localStorage.getItem("adminExchangeRate") || "1");
    const statsData = await get("stats"); if (statsData) setStats(statsData);
    const financeData = await get("finance"); if (financeData) setFinance(financeData);
    const usersData = await get("users"); if (usersData) setUsers(usersData);
    const priceData = await get("pricing"); if (priceData) setPrices(priceData);
    const groupData = await get("pricing-groups"); if (groupData) setGroups(groupData);
    const multiplierData = await get("model-multipliers"); if (multiplierData) setMultipliers(multiplierData);
    const routeData = await get("supplier-routes"); if (routeData) setSupplierRoutes(routeData);
    const ledgerData = await get("ledger"); if (ledgerData) setLedger(ledgerData);
    const analyticData = await get(`analytics/series?range=${analyticsRange}`); if (analyticData) setAnalyticsSeries(analyticData);
  }, [get, analyticsRange]);

  useEffect(() => { loadAll(); }, [loadAll]);

  useEffect(() => {
    const loadAnalytics = async () => {
      const data = await get(`analytics/series?range=${analyticsRange}`);
      if (data) setAnalyticsSeries(data);
    };
    loadAnalytics();
  }, [analyticsRange, get]);

  const post = useCallback(async (path: string, body: any, done: () => Promise<void> | void) => {
    const token = localStorage.getItem("token");
    if (!token) return;
    setError(""); setMessage("");
    const response = await fetch(`${API}/admin/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await response.json();
    if (response.ok) { setMessage(data.message || "操作成功"); await done(); }
    else setError(data.detail || "操作失败");
    return data as any;
  }, []);

  const remove = useCallback(async (path: string, done: () => Promise<void> | void) => {
    const token = localStorage.getItem("token");
    if (!token) return;
    setError(""); setMessage("");
    const response = await fetch(`${API}/admin/${path}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
    const data = await response.json();
    if (response.ok) { setMessage(data.message || "已删除"); await done(); }
    else setError(data.detail || "删除失败");
  }, []);

  const submitRoute = async () => {
    if (!newRoute.model_name.trim() || !newRoute.upstream_model.trim() || !newRoute.endpoint_url.trim() || !newRoute.api_key) return;
    await post("supplier-routes", newRoute, async () => {
      setNewRoute({ model_name: "", upstream_model: "", endpoint_url: "", api_key: "" });
      await loadAll();
    });
  };

  const saveRoute = async () => {
    if (!editRoute) return;
    await post(`supplier-routes/${editRoute.id}`, {
      upstream_model: editRoute.upstream_model,
      endpoint_url: editRoute.endpoint_url,
      api_key: editRouteKey || undefined,
    }, async () => {
      setEditRoute(null); setEditRouteKey("");
      await loadAll();
    });
  };

  const resetTestAccounting = async () => {
    if (!window.confirm("确认重置测试账本吗？会清空用量记录和账本，并把所有客户余额设为 RM 0。")) return;
    await post("accounting/reset", undefined, loadAll);
  };

  const adjustBalance = async (userId: number) => {
    await post("users/adjust-balance", { user_id: userId, amount: Number(adjustAmount), reason: adjustReason || "管理员调整" }, async () => {
      setAdjustUser(null); setAdjustAmount(""); setAdjustReason("");
      await loadUsers(search, statusFilter);
    });
  };

  const toggleFlag = async (userId: number, flagged: boolean) => {
    await post(`users/${userId}/risk-flag`, { flagged, reason: flagReason || "风险复查" }, async () => {
      setFlagUser(null); setFlagReason(""); await loadUsers(search, statusFilter);
    });
  };

  const toggleSuspend = async (userId: number, currentStatus: string) => {
    const action = currentStatus === "suspended" ? `users/${userId}/activate` : `users/${userId}/suspend`;
    const body = currentStatus === "suspended" ? undefined : { reason: "管理员操作" };
    await post(action, body, async () => { await loadUsers(search, statusFilter); });
  };

  const createGroup = async () => {
    const name = groupName.trim();
    if (!name) return;
    await post("pricing-groups", { name }, async () => {
      setGroupName("");
      setSelectedGroup(name);
      await loadAll();
    });
  };

  const renameGroup = async () => {
    const name = groupName.trim();
    if (!name || !selectedGroupObject) return;
    await post(`pricing-groups/${selectedGroupObject.id}/rename`, { name }, async () => {
      setGroupName("");
      setSelectedGroup(name);
      await loadAll();
    });
  };

  const removeGroup = async () => {
    if (!selectedGroupObject) return;
    if (!window.confirm(`确定删除组别 ${selectedGroupObject.name} 吗？`)) return;
    await remove(`pricing-groups/${selectedGroupObject.id}`, async () => {
      setSelectedGroup("");
      setGroupName("");
      await loadAll();
    });
  };

  const movePrice = async (price: PriceRow, groupNameValue: string) => {
    if (!groupNameValue || groupNameValue === price.group_name) return;
    await post("pricing", {
      model: price.model,
      input_cost_per_token: price.input_cost ?? 0,
      output_cost_per_token: price.output_cost ?? 0,
      cache_write_cost_per_token: price.cache_write_cost ?? 0,
      cache_read_cost_per_token: price.cache_read_cost ?? 0,
      input_sell_per_token: price.input_sell ?? 0,
      output_sell_per_token: price.output_sell ?? 0,
      cache_write_sell_per_token: price.cache_write_sell ?? 0,
      cache_read_sell_per_token: price.cache_read_sell ?? 0,
      group_name: groupNameValue,
    }, async () => { await loadAll(); });
  };

  const savePrice = async () => {
    if (!editPrice) return;
    await post("pricing", {
      model: editPrice.model,
      input_cost_per_token: editPrice.input_cost ?? 0,
      output_cost_per_token: editPrice.output_cost ?? 0,
      input_sell_per_token: editPrice.input_sell ?? 0,
      output_sell_per_token: editPrice.output_sell ?? 0,
      cache_write_sell_per_token: editPrice.cache_write_sell ?? 0,
      cache_read_sell_per_token: editPrice.cache_read_sell ?? 0,
      cache_write_cost_per_token: editPrice.cache_write_cost ?? 0,
      cache_read_cost_per_token: editPrice.cache_read_cost ?? 0,
      group_name: editPrice.group_name,
    }, async () => {
      setEditPrice(null);
      const refreshed = await get("pricing"); if (refreshed) setPrices(refreshed);
    });
  };

  const createPrice = async () => {
    const model = newPrice.model.trim();
    if (!model) return;
    if (prices.some((item) => item.model.toLowerCase() === model.toLowerCase())) {
      setError("这个模型已经存在");
      return;
    }
    await post("pricing", {
      model,
      input_cost_per_token: 0,
      output_cost_per_token: 0,
      input_sell_per_token: Number(newPrice.input_sell || 0),
      output_sell_per_token: Number(newPrice.output_sell || 0),
      cache_write_sell_per_token: Number(newPrice.cache_write || 0),
      cache_read_sell_per_token: Number(newPrice.cache_read || 0),
      group_name: selectedGroupValue,
    }, async () => {
      setNewPrice({ model: "", input_sell: "", output_sell: "", cache_write: "", cache_read: "" });
      setShowModelModal(false);
      const refreshed = await get("pricing");
      if (refreshed) setPrices(refreshed);
    });
  };

  const openDetail = async (userId: number) => {
    const result = await get(`users/${userId}`);
    if (result) { setDetail(result); setTab("detail"); }
  };

  const openMultiplier = async (model: string) => {
    const base = new Date();
    const dates = Array.from({ length: 3 }, (_, index) => {
      const value = new Date(base);
      value.setDate(base.getDate() + index);
      return value.toISOString().slice(0, 10);
    });
    const dayRows = await Promise.all(dates.map(async (date) => {
      const result = await get(`model-multiplier-day?model=${encodeURIComponent(model)}&business_date=${date}`) as HourlyMultiplierRow | null;
      return result || { model, business_date: date, hourly_multipliers: [] };
    }));
    setMultiplierDate(dates[0]);
    setEditMultiplier(dayRows[0]);
    setMultiplierDays(dayRows);
  };

  const saveMultiplier = async () => {
    if (!editMultiplier) return;
    await post("model-multiplier-day", editMultiplier, async () => {
      setEditMultiplier(null);
      setMultiplierDays((rows) => rows.map((row) => row.business_date === editMultiplier.business_date ? editMultiplier : row));
    });
  };

  const tabs = [
    { id: "stats", label: "总览" },
    { id: "users", label: "用户" },
    { id: "pricing", label: "模型管理" },
    { id: "suppliers", label: "模型连接" },
    { id: "analytics", label: "数据统计" },
    { id: "ledger", label: "账本" },
    { id: "audit", label: "审计" },
  ];
  const activeTab = tabs.find((item) => item.id === tab) || tabs[0];
  const adminTabIcons: Record<string, React.ReactNode> = {
    stats: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3.5" y="3.5" width="17" height="17" rx="5"/><path d="M8 15.5v-5M12 15.5V8.5M16 15.5v-3"/></svg>),
    users: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="8.5" r="3.5"/><path d="M3.5 19.5c.6-3.1 2.9-5 5.5-5s4.9 1.9 5.5 5"/><path d="M16.5 5.2a3.3 3.3 0 0 1 0 6.6M15.8 14.5c1.9.4 3.5 2 3.9 4.6"/></svg>),
    pricing: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3.5" y="3.5" width="17" height="17" rx="4"/><path d="M8 9h8M8 13h8M8 17h4"/></svg>),
    suppliers: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M7 8h10M7 12h10M7 16h6"/><rect x="3.5" y="4.5" width="17" height="15" rx="4"/></svg>),
    analytics: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M4 18.5V10M9.5 18.5V6M15 18.5v-6M20.5 18.5V9"/></svg>),
    ledger: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M6 3.5h12a2 2 0 0 1 2 2v15H8a2 2 0 0 1-2-2Z"/><path d="M9.5 8.5h7M9.5 12.5h7M9.5 16.5h4"/></svg>),
    audit: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Z"/><path d="M15.8 15.8 20.5 20.5"/></svg>),
  };
  const selectedGroupObject = groups.find((group) => group.name === selectedGroup) || groups[0] || null;
  const exchangeRateValue = Number(exchangeRate) || 1;
  const analyticsBucketCount = analyticsRange === "today" ? 24 : analyticsRange === "month" ? 31 : 12;
  const analyticsLabels = (() => {
    if (analyticsSeries?.buckets?.length) return analyticsSeries.buckets;
    if (analyticsRange === "today") return Array.from({ length: 24 }, (_, hour) => `${String(hour).padStart(2, "0")}:00`);
    if (analyticsRange === "month") return Array.from({ length: 31 }, (_, day) => String(day + 1));
    return Array.from({ length: 12 }, (_, month) => `${month + 1}月`);
  })();
  const zeroSeries = () => Array.from({ length: analyticsBucketCount }, () => 0);
  const groupDatasets = analyticsSeries?.groups?.length
    ? analyticsSeries.groups.map((group, index) => ({
        label: group.name,
        data: group.series.length ? group.series : zeroSeries(),
        borderColor: ["#465fff", "#12b76a", "#f79009", "#7a95ff", "#f04438"][index % 5],
        backgroundColor: ["rgba(70, 95, 255, .12)", "rgba(18, 183, 106, .12)", "rgba(247, 144, 9, .12)", "rgba(122, 149, 255, .12)", "rgba(240, 68, 56, .12)"][index % 5],
        tension: 0.3,
        borderWidth: 2,
      }))
    : [{ label: "无数据", data: zeroSeries(), borderColor: "#64748b", backgroundColor: "rgba(100, 116, 139, .12)", tension: 0.3, borderWidth: 2 }];
  const selectedGroupValue = selectedGroupObject?.name || "";
  const sortedPrices = [...prices].sort((first, second) => {
    if (sortMode === "group") {
      const firstGroup = first.group_name || "";
      const secondGroup = second.group_name || "";
      return firstGroup.localeCompare(secondGroup, "zh-Hans-CN") || first.model.localeCompare(second.model, "zh-Hans-CN");
    }
    return first.model.localeCompare(second.model, "zh-Hans-CN");
  });

  return (
    <AppShell
      active="/admin"
      mode="admin"
      email={email}
      title="管理员后台"
      subtitle={`当前页面：${activeTab.label} · 用户、收入、定价、模型连接、账本和审计`}
      actions={(
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div>
            <div className="stat-label">汇率（1 CNY = RM）</div>
            <input
              className="input"
              style={{ width: 110, height: 34, fontSize: 12.5 }}
              type="number"
              step="0.0001"
              min="0"
              value={exchangeRate}
              onChange={(event) => {
                setExchangeRate(event.target.value);
                if (typeof window !== "undefined") {
                  localStorage.setItem("adminExchangeRate", event.target.value);
                }
              }}
            />
          </div>
          <button className="button button-secondary" onClick={async () => { await loadAll(); setMessage("数据已刷新"); }}>刷新数据</button>
        </div>
      )}
    >
      {error && <div className="notice notice-danger" style={{ marginBottom: 15 }}>{error}</div>}
      {message && <div className="notice notice-success" style={{ marginBottom: 15 }}>{message}</div>}
      <div className="admin-tabbar">
        <div className="admin-tabbar-inner">
          {tabs.map((item) => (
            <button
              key={item.id}
              className={`admin-tab${tab === item.id ? " active" : ""}`}
              aria-current={tab === item.id ? "page" : undefined}
              onClick={() => { setTab(item.id); setDetail(null); }}
            >
              <span className="admin-tab-icon" aria-hidden>{adminTabIcons[item.id]}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </div>

      {tab === "stats" && stats && finance && (
        <>
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10 }}>
          <button className="button button-danger" onClick={resetTestAccounting}>重置测试账本</button>
        </div>
        <div className="grid grid-4">
          <div className="card"><div className="metric-label">已激活用户</div><div className="metric-value">{stats.active_users}</div></div>
          <div className="card"><div className="metric-label">已激活 Key</div><div className="metric-value">{stats.active_api_keys}</div></div>
          <div className="card"><div className="metric-label">客户总余额</div><div className="metric-value">RM {finance.total_customer_wallet_balance.toFixed(2)}</div></div>
          <div className="card"><div className="metric-label">已用成本</div><div className="metric-value">RM {(finance.total_supplier_cost_cny * exchangeRateValue).toFixed(2)}</div></div>
        </div>
        </>
      )}

      {tab === "users" && (
        <div className="card">
          <div className="card-title"><h2 className="section-title">用户管理</h2><span className="stat-mini">{users.length} 个用户</span></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 170px auto", gap: 10, marginBottom: 14 }}>
            <input className="input" placeholder="搜索邮箱…" value={search} onChange={(event) => setSearch(event.target.value)} />
            <select className="select" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">全部状态</option><option value="active">可用</option><option value="suspended">已封禁</option>
            </select>
            <button className="button button-secondary" onClick={() => loadUsers(search, statusFilter)}>搜索</button>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>ID</th><th>邮箱</th><th>状态</th><th>余额</th><th>Key</th><th>套餐</th><th>请求</th><th>操作</th></tr></thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.id}</td>
                    <td><button className="button button-ghost" style={{ padding: 0 }} onClick={() => openDetail(user.id)}>{user.email}</button>{user.risk_flag && <span className="badge badge-warning" style={{ marginLeft: 8 }}>风险</span>}</td>
                    <td><span className={`badge ${user.status === "active" ? "badge-active" : "badge-danger"}`}>{user.status === "active" ? "可用" : "已封禁"}</span></td>
                    <td>RM {user.balance.toFixed(2)}</td><td>{user.active_keys}</td><td>{user.active_plans}</td><td>{user.total_requests}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <button className="button button-secondary" onClick={() => { setAdjustUser(user.id); setAdjustAmount(""); }}>调整余额</button>{" "}
                      <button className="button button-secondary" onClick={() => { setFlagUser(user.id); setFlagReason(""); }}>{user.risk_flag ? "清除" : "标记"}</button>{" "}
                      <button className="button button-danger" onClick={() => toggleSuspend(user.id, user.status)}>{user.status === "suspended" ? "解封" : "封禁"}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {users.length === 0 && <div className="empty">没有找到用户。</div>}
          {adjustUser !== null && (
            <div className="notice" style={{ marginTop: 15 }}>
              <strong>调整用户 #{adjustUser} 的余额</strong>
              <div style={{ display: "grid", gridTemplateColumns: "150px 1fr auto", gap: 8, marginTop: 10 }}>
                <input className="input" type="number" step="0.01" value={adjustAmount} placeholder="金额" onChange={(event) => setAdjustAmount(event.target.value)} />
                <input className="input" value={adjustReason} placeholder="原因" onChange={(event) => setAdjustReason(event.target.value)} />
                <button className="button button-primary" onClick={() => adjustBalance(adjustUser)}>保存</button>
              </div>
            </div>
          )}
          {flagUser !== null && (
            <div className="notice" style={{ marginTop: 15 }}>
              <strong>用户 #{flagUser} 风险复查</strong>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, marginTop: 10 }}>
                <input className="input" value={flagReason} placeholder="原因" onChange={(event) => setFlagReason(event.target.value)} />
                <button className="button button-warning" onClick={() => toggleFlag(flagUser, !users.find((user) => user.id === flagUser)?.risk_flag)}>保存</button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "detail" && detail && (
        <div className="grid">
          <div className="card">
            <div className="card-title">
              <div><h2 className="section-title">{detail.user.email}</h2><div className="stat-mini">#{detail.user.id} · {detail.user.status === "active" ? "可用" : "已封禁"} · 注册 {new Date(detail.user.created_at).toLocaleDateString()}</div></div>
              <button className="button button-secondary" onClick={() => setTab("users")}>返回用户</button>
            </div>
            <div className="grid grid-2">
              <div className="card"><div className="metric-label">可用余额</div><div className="metric-value">RM {detail.wallet.available.toFixed(2)}</div></div>
              <div className="card"><div className="metric-label">已预留</div><div className="metric-value">RM {detail.wallet.reserved.toFixed(2)}</div></div>
            </div>
          </div>
          <div className="grid grid-2">
            <div className="card"><h3 className="section-title">API Keys</h3>{detail.keys.map((key) => <div key={key.id} className="notice" style={{ marginBottom: 8 }}><code className="mono">{key.prefix}…</code> · {key.status === "active" ? "可用" : "已撤销"} · {key.name}</div>)}{detail.keys.length === 0 && <div className="empty">没有 Key</div>}</div>
            <div className="card"><h3 className="section-title">套餐权益</h3>{detail.entitlements.map((item) => <div key={item.id} className="notice" style={{ marginBottom: 8 }}>套餐 #{item.plan_id} · {item.status} · 到期 {new Date(item.expires_at).toLocaleDateString()}</div>)}{detail.entitlements.length === 0 && <div className="empty">没有套餐</div>}</div>
            <div className="card"><h3 className="section-title">最近用量</h3>{detail.recent_usage.map((item) => <div key={item.id} className="notice" style={{ marginBottom: 8 }}>{new Date(item.created_at).toLocaleString()} · {item.model} · {item.input_tokens}/{item.output_tokens} · RM {item.cost.toFixed(2)}</div>)}{detail.recent_usage.length === 0 && <div className="empty">没有用量</div>}</div>
            <div className="card"><h3 className="section-title">最近账本</h3>{detail.recent_ledger.map((item) => <div key={item.id} className="notice" style={{ marginBottom: 8 }}>{new Date(item.created_at).toLocaleString()} · {item.type} · RM {item.amount.toFixed(2)} → RM {item.balance_after.toFixed(2)}</div>)}{detail.recent_ledger.length === 0 && <div className="empty">没有账本记录</div>}</div>
          </div>
        </div>
      )}

      {tab === "pricing" && (
        <div className="card">
          <div className="card-title">
            <div>
              <h2 className="section-title">模型管理</h2>
              <div className="stat-mini">价格单位 RM · 成本按汇率换算</div>
            </div>
            <button className="button button-primary" onClick={() => setShowModelModal(true)}>创建模型</button>
          </div>

          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <button className="button button-secondary" onClick={() => setSortMode("group")}>组别排序</button>
            <button className="button button-secondary" onClick={() => setSortMode("model")}>模型排序</button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "220px 1fr auto auto auto", gap: 8, marginBottom: 16 }}>
            <select
              className="select"
              value={selectedGroup}
              onChange={(event) => { setSelectedGroup(event.target.value); setGroupName(event.target.value); }}
            >
              <option value="">选择组别</option>
              {groups.map((group) => <option key={group.id} value={group.name}>{group.name}</option>)}
            </select>
            <input className="input" value={groupName} placeholder="组别名称" onChange={(event) => setGroupName(event.target.value)} />
            <button className="button button-primary" onClick={createGroup} disabled={!groupName.trim()}>创建</button>
            <button className="button button-secondary" onClick={renameGroup} disabled={!selectedGroupObject || !groupName.trim()}>编辑</button>
            <button className="button button-danger" onClick={removeGroup} disabled={!selectedGroupObject}>删除</button>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>模型</th><th>组别</th><th>输入售价</th><th>输入成本</th><th>输出售价</th>
                  <th>输出成本（RM）</th><th>缓存创建售价</th><th>缓存创建成本</th><th>缓存读取售价</th>
                  <th>缓存读取成本（RM）</th><th>操作</th>
                </tr>
              </thead>
              <tbody>
                {sortedPrices.map((price) => (
                  <tr key={price.model}>
                    <td><code className="mono">{price.model}</code></td>
                    <td>
                      <select
                        className="select"
                        value={price.group_name || ""}
                        onChange={(event) => movePrice(price, event.target.value)}
                      >
                        <option value="">未分组</option>
                        {groups.map((group) => <option key={group.id} value={group.name}>{group.name}</option>)}
                      </select>
                    </td>
                    <td>RM {(price.input_sell ?? 0).toFixed(2)}</td>
                    <td>RM {((price.input_cost ?? 0) * exchangeRateValue).toFixed(2)}</td>
                    <td>RM {(price.output_sell ?? 0).toFixed(2)}</td>
                    <td>RM {((price.output_cost ?? 0) * exchangeRateValue).toFixed(2)}</td>
                    <td>RM {(price.cache_write_sell ?? 0).toFixed(2)}</td>
                    <td>RM {((price.cache_write_cost ?? 0) * exchangeRateValue).toFixed(2)}</td>
                    <td>RM {(price.cache_read_sell ?? 0).toFixed(2)}</td>
                    <td>RM {((price.cache_read_cost ?? 0) * exchangeRateValue).toFixed(2)}</td>
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      <button
                        className="button button-ghost"
                        onClick={() => setEditPrice({
                          ...price,
                          input_cost: price.input_cost ?? 0,
                          output_cost: price.output_cost ?? 0,
                          cache_write_cost: price.cache_write_cost ?? 0,
                          cache_read_cost: price.cache_read_cost ?? 0,
                          input_sell: price.input_sell ?? 0,
                          output_sell: price.output_sell ?? 0,
                          cache_write_sell: price.cache_write_sell ?? 0,
                          cache_read_sell: price.cache_read_sell ?? 0,
                        })}
                      >
                        编辑
                      </button>{" "}
                      <button className="button button-secondary" onClick={() => openMultiplier(price.model)}>峰谷倍数</button>{" "}
                      <button className="button button-danger" onClick={() => setDeletePrice(price)}>删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {sortedPrices.length === 0 && <div className="empty">还没有模型。</div>}
        </div>
      )}

      {tab === "analytics" && (
        <div className="card">
          <div className="card-title">
            <div>
              <h2 className="section-title">数据统计</h2>
              <div className="stat-mini">全部单位按 RM / Token 统计</div>
            </div>
            <select className="select" style={{ width: 130 }} value={analyticsRange} onChange={(event) => setAnalyticsRange(event.target.value as "today" | "month" | "year")}>
              <option value="today">今日</option>
              <option value="month">本月</option>
              <option value="year">今年</option>
            </select>
          </div>
          <div className="grid grid-2" style={{ marginTop: 15 }}>
            <div className="card">
              <div className="card-title"><h3 className="section-title">所有用户用量</h3><span className="stat-mini">输入 / 输出 / 缓存创建 / 缓存读取</span></div>
                <div style={{ height: 300, position: "relative" }}>
                  <Line
                    data={{
                      labels: analyticsLabels,
                      datasets: [
                        { label: "输入", data: analyticsSeries?.usage?.input?.length ? analyticsSeries.usage.input : zeroSeries(), borderColor: "#465fff", backgroundColor: "rgba(70, 95, 255, .12)", tension: 0.3, borderWidth: 2 },
                        { label: "输出", data: analyticsSeries?.usage?.output?.length ? analyticsSeries.usage.output : zeroSeries(), borderColor: "#12b76a", backgroundColor: "rgba(18, 183, 106, .12)", tension: 0.3, borderWidth: 2 },
                        { label: "缓存创建", data: analyticsSeries?.usage?.cache_write?.length ? analyticsSeries.usage.cache_write : zeroSeries(), borderColor: "#f79009", backgroundColor: "rgba(247, 144, 9, .12)", tension: 0.3, borderWidth: 2 },
                        { label: "缓存读取", data: analyticsSeries?.usage?.cache_read?.length ? analyticsSeries.usage.cache_read : zeroSeries(), borderColor: "#7a95ff", backgroundColor: "rgba(122, 149, 255, .12)", tension: 0.3, borderWidth: 2 },
                      ],
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      interaction: { mode: "index", intersect: false },
                      plugins: { legend: { position: "top", labels: { boxWidth: 10 } } },
                      scales: {
                        x: { title: { display: true, text: analyticsRange === "today" ? "时间（小时）" : analyticsRange === "month" ? "日期" : "月份" }, grid: { display: false } },
                        y: { title: { display: true, text: "Token" }, beginAtZero: true, grid: { color: "rgba(0,0,0,.06)" } },
                      },
                    }}
                  />
                </div>
            </div>
            <div className="card">
              <div className="card-title"><h3 className="section-title">客户总余额</h3><span className="stat-mini">RM</span></div>
                <div style={{ height: 300, position: "relative" }}>
                  <Line
                    data={{
                      labels: analyticsLabels,
                      datasets: [{ label: "客户总余额", data: analyticsSeries?.wallet_balance?.length ? analyticsSeries.wallet_balance : zeroSeries(), borderColor: "#12b76a", backgroundColor: "rgba(18, 183, 106, .12)", tension: 0.3, borderWidth: 2, fill: true }],
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      interaction: { mode: "index", intersect: false },
                      plugins: { legend: { position: "top", labels: { boxWidth: 10 } } },
                      scales: {
                        x: { title: { display: true, text: analyticsRange === "today" ? "时间（小时）" : analyticsRange === "month" ? "日期" : "月份" }, grid: { display: false } },
                        y: { title: { display: true, text: "RM" }, beginAtZero: true, grid: { color: "rgba(0,0,0,.06)" } },
                      },
                    }}
                  />
                </div>
            </div>
          </div>
          <div className="grid grid-2" style={{ marginTop: 15 }}>
            <div className="card">
              <div className="card-title"><h3 className="section-title">分组使用率</h3><span className="stat-mini">按 Token</span></div>
                <div style={{ height: 300, position: "relative" }}>
                  <Line
                    data={{
                      labels: analyticsLabels,
                      datasets: groupDatasets,
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      interaction: { mode: "index", intersect: false },
                      plugins: { legend: { position: "top", labels: { boxWidth: 10 } } },
                      scales: {
                        x: { title: { display: true, text: analyticsRange === "today" ? "时间（小时）" : analyticsRange === "month" ? "日期" : "月份" }, grid: { display: false } },
                        y: { title: { display: true, text: "Token" }, beginAtZero: true, grid: { color: "rgba(0,0,0,.06)" } },
                      },
                    }}
                  />
                </div>
            </div>
            <div className="card">
              <div className="card-title"><h3 className="section-title">扣除成本后盈利</h3><span className="stat-mini">RM</span></div>
                <div style={{ height: 300, position: "relative" }}>
                  <Line
                    data={{
                      labels: analyticsLabels,
                      datasets: [{ label: "RM", data: analyticsSeries?.revenue?.length ? analyticsSeries.revenue.map((value, index) => Number((value - (analyticsSeries.supplier_cost?.[index] ?? 0) * exchangeRateValue).toFixed(2))) : zeroSeries(), borderColor: "#f04438", backgroundColor: "rgba(240, 68, 56, .12)", tension: 0.3, borderWidth: 2, fill: true }],
                    }}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      interaction: { mode: "index", intersect: false },
                      plugins: { legend: { position: "top", labels: { boxWidth: 10 } } },
                      scales: {
                        x: { title: { display: true, text: analyticsRange === "today" ? "时间（小时）" : analyticsRange === "month" ? "日期" : "月份" }, grid: { display: false } },
                        y: { title: { display: true, text: "RM" }, beginAtZero: true, grid: { color: "rgba(0,0,0,.06)" } },
                      },
                    }}
                  />
                </div>
            </div>
          </div>
        </div>
      )}

      {tab === "suppliers" && (
        <div className="card">
          <div className="card-title">
            <div><h2 className="section-title">出售模型 → 供应商模型</h2><div className="stat-mini">只连接，不填写协议；协议会由端点自动识别</div></div>
            <span className="stat-mini">{supplierRoutes.length} 条连接</span>
          </div>
          <div className="notice" style={{ marginBottom: 14 }}>客户请求 → 中转站鉴权和计费 → 供应商端点与密钥 → 上游模型返回。</div>
          <div className="grid grid-4">
            <div>
              <label className="label">出售模型</label>
              <select className="select" value={newRoute.model_name} onChange={(event) => setNewRoute({ ...newRoute, model_name: event.target.value })}>
                <option value="">选择已创建模型</option>
                {prices.filter((item) => item.group_name).map((item) => <option key={item.model} value={item.model}>{item.model}</option>)}
              </select>
            </div>
            <div><label className="label">上游模型 ID</label><input className="input" value={newRoute.upstream_model} placeholder="供应商实际模型名" onChange={(event) => setNewRoute({ ...newRoute, upstream_model: event.target.value })} /></div>
            <div><label className="label">上游 API Key</label><input className="input" type="password" value={newRoute.api_key} placeholder="保存后加密" onChange={(event) => setNewRoute({ ...newRoute, api_key: event.target.value })} /></div>
            <div><label className="label">上游端点</label><input className="input" value={newRoute.endpoint_url} placeholder="https://..." onChange={(event) => setNewRoute({ ...newRoute, endpoint_url: event.target.value })} /></div>
            <div style={{ gridColumn: "span 4" }}><button className="button button-primary" onClick={submitRoute} disabled={!newRoute.model_name || !newRoute.upstream_model || !newRoute.api_key || !newRoute.endpoint_url}>连接模型</button></div>
          </div>
          <div className="table-wrap" style={{ marginTop: 15 }}>
            <table className="data-table">
              <thead><tr><th>出售模型</th><th>上游模型</th><th>API Key</th><th>上游端点</th><th>操作</th></tr></thead>
              <tbody>
                {supplierRoutes.map((route) => (
                  <tr key={route.id}>
                    <td><strong>{route.model_name}</strong></td>
                    <td><code className="mono">{route.upstream_model}</code></td>
                    <td><span className="badge badge-info">····{route.api_key_last4}</span></td>
                    <td style={{ maxWidth: 320 }}><code className="mono">{route.endpoint_url}</code></td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <button className="button button-secondary" onClick={() => { setEditRoute({ ...route }); setEditRouteKey(""); }}>编辑</button>{" "}
                      <button className="button button-danger" onClick={() => remove(`supplier-routes/${route.id}`, loadAll)}>删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {supplierRoutes.length === 0 && <div className="empty">还没有连接。先在“模型定价”创建出售模型。</div>}
          {editRoute && (
            <div className="notice" style={{ marginTop: 15 }}>
              <strong>编辑连接 · {editRoute.model_name}</strong>
              <div className="grid grid-4" style={{ marginTop: 10 }}>
                <div><label className="label">上游模型 ID</label><input className="input" value={editRoute.upstream_model} onChange={(event) => setEditRoute({ ...editRoute, upstream_model: event.target.value })} /></div>
                <div style={{ gridColumn: "span 2" }}><label className="label">上游端点</label><input className="input" value={editRoute.endpoint_url} onChange={(event) => setEditRoute({ ...editRoute, endpoint_url: event.target.value })} /></div>
                <div><label className="label">替换 API Key</label><input className="input" type="password" value={editRouteKey} placeholder="留空则不更换" onChange={(event) => setEditRouteKey(event.target.value)} /></div>
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button className="button button-primary" onClick={saveRoute}>保存</button>
                <button className="button button-secondary" onClick={() => { setEditRoute(null); setEditRouteKey(""); }}>取消</button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "ledger" && (
        <div className="card">
          <div className="card-title"><h2 className="section-title">钱包账本</h2><span className="stat-mini">{ledger.length} 条记录</span></div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>时间</th><th>用户</th><th>类型</th><th>金额</th><th>变动后余额</th><th>引用</th></tr></thead>
              <tbody>
                {ledger.map((entry) => (
                  <tr key={entry.id}>
                    <td>{new Date(entry.created_at).toLocaleString()}</td><td>#{entry.user_id}</td><td><code className="mono">{entry.type}</code></td>
                    <td style={{ color: entry.amount >= 0 ? "var(--success)" : "var(--danger)" }}>{entry.amount >= 0 ? "+" : ""}{entry.amount.toFixed(2)}</td>
                    <td>RM {entry.balance_after.toFixed(2)}</td><td>{entry.reference}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "audit" && (
        <div className="card">
          <div className="card-title"><h2 className="section-title">审计日志</h2><span className="stat-mini">{audit.length} 条事件</span></div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>时间</th><th>管理员</th><th>操作</th><th>对象</th><th>详情</th></tr></thead>
              <tbody>
                {audit.map((entry) => (
                  <tr key={entry.id}>
                    <td>{new Date(entry.created_at).toLocaleString()}</td><td>{entry.admin}</td><td><code className="mono">{entry.action}</code></td>
                    <td>{entry.target_type} #{entry.target_id}</td><td>{entry.detail || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {showGroupModal && (
        <div className="modal-overlay" onClick={() => setShowGroupModal(false)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="card-title"><strong>创建组别</strong><button className="button button-ghost" onClick={() => setShowGroupModal(false)}>×</button></div>
            <label className="label">组别名称</label>
            <input className="input" value={groupName} placeholder="例如 Zhipu GLM" onChange={(event) => setGroupName(event.target.value)} />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button className="button button-secondary" onClick={() => setShowGroupModal(false)}>取消</button>
              <button className="button button-primary" onClick={async () => { if (!groupName.trim()) return; const created = await post("pricing-groups", { name: groupName.trim() }, loadAll); if (created?.name) { setSelectedGroup(created.name); } setShowGroupModal(false); }} disabled={!groupName.trim()}>创建</button>
            </div>
          </div>
        </div>
      )}
      {deleteGroup && (
        <div className="modal-overlay" onClick={() => setDeleteGroup(null)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="card-title"><strong>删除组别</strong><button className="button button-ghost" onClick={() => setDeleteGroup(null)}>×</button></div>
            <div className="notice notice-danger">确定删除 {deleteGroup.name} 吗？只有空组别才能删除，操作不可恢复。</div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button className="button button-secondary" onClick={() => setDeleteGroup(null)}>取消</button>
              <button className="button button-danger" onClick={async () => { await remove(`pricing-groups/${deleteGroup.id}`, loadAll); setDeleteGroup(null); }}>确认删除</button>
            </div>
          </div>
        </div>
      )}
      {showModelModal && (
        <div className="modal-overlay" onClick={() => setShowModelModal(false)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="card-title"><strong>创建模型</strong><button className="button button-ghost" onClick={() => setShowModelModal(false)}>×</button></div>
            <div className="stat-mini">加入分组：{selectedGroupValue || "请先选择组别"}</div>
            <label className="label" style={{ marginTop: 15 }}>模型 ID</label>
            <input className="input" value={newPrice.model} placeholder="例如 glm-5.3" onChange={(event) => setNewPrice({ ...newPrice, model: event.target.value })} />
            <div className="grid grid-2">
              <div><label className="label">输入售价（RM）</label><input className="input" type="number" step="0.000001" value={newPrice.input_sell} onChange={(event) => setNewPrice({ ...newPrice, input_sell: event.target.value })} /></div>
              <div><label className="label">输出售价（RM）</label><input className="input" type="number" step="0.000001" value={newPrice.output_sell} onChange={(event) => setNewPrice({ ...newPrice, output_sell: event.target.value })} /></div>
              <div><label className="label">缓存创建售价（RM）</label><input className="input" type="number" step="0.000001" value={newPrice.cache_write} onChange={(event) => setNewPrice({ ...newPrice, cache_write: event.target.value })} /></div>
              <div><label className="label">缓存读取售价（RM）</label><input className="input" type="number" step="0.000001" value={newPrice.cache_read} onChange={(event) => setNewPrice({ ...newPrice, cache_read: event.target.value })} /></div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button className="button button-secondary" onClick={() => setShowModelModal(false)}>取消</button>
              <button className="button button-primary" onClick={createPrice} disabled={!newPrice.model.trim()}>创建</button>
            </div>
          </div>
        </div>
      )}
      {editPrice && (
        <div className="modal-overlay" onClick={() => setEditPrice(null)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="card-title"><strong>编辑模型 · {editPrice.model}</strong><button className="button button-ghost" onClick={() => setEditPrice(null)}>×</button></div>
            <label className="label">分组</label>
            <select className="select" value={editPrice.group_name || ""} onChange={(event) => setEditPrice({ ...editPrice, group_name: event.target.value })}>
              <option value="">请选择分组</option>
              {groups.map((group) => <option key={group.id} value={group.name}>{group.name}</option>)}
            </select>
            <div className="grid grid-2">
              <div><label className="label">输入售价（RM）</label><input className="input" type="number" step="0.000001" value={editPrice.input_sell} onChange={(event) => setEditPrice({ ...editPrice, input_sell: Number(event.target.value) })} /></div>
              <div><label className="label">输入成本（CNY）</label><input className="input" type="number" step="0.000001" value={editPrice.input_cost ?? 0} onChange={(event) => setEditPrice({ ...editPrice, input_cost: Number(event.target.value) })} /></div>
              <div><label className="label">输出售价（RM）</label><input className="input" type="number" step="0.000001" value={editPrice.output_sell} onChange={(event) => setEditPrice({ ...editPrice, output_sell: Number(event.target.value) })} /></div>
              <div><label className="label">输出成本（CNY）</label><input className="input" type="number" step="0.000001" value={editPrice.output_cost ?? 0} onChange={(event) => setEditPrice({ ...editPrice, output_cost: Number(event.target.value) })} /></div>
              <div><label className="label">缓存创建售价（RM）</label><input className="input" type="number" step="0.000001" value={editPrice.cache_write_sell ?? 0} onChange={(event) => setEditPrice({ ...editPrice, cache_write_sell: Number(event.target.value) })} /></div>
              <div><label className="label">缓存创建成本（CNY）</label><input className="input" type="number" step="0.000001" value={editPrice.cache_write_cost ?? 0} onChange={(event) => setEditPrice({ ...editPrice, cache_write_cost: Number(event.target.value) })} /></div>
              <div><label className="label">缓存读取售价（RM）</label><input className="input" type="number" step="0.000001" value={editPrice.cache_read_sell ?? 0} onChange={(event) => setEditPrice({ ...editPrice, cache_read_sell: Number(event.target.value) })} /></div>
              <div><label className="label">缓存读取成本（CNY）</label><input className="input" type="number" step="0.000001" value={editPrice.cache_read_cost ?? 0} onChange={(event) => setEditPrice({ ...editPrice, cache_read_cost: Number(event.target.value) })} /></div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button className="button button-secondary" onClick={() => setEditPrice(null)}>取消</button>
              <button className="button button-primary" onClick={savePrice}>保存</button>
            </div>
          </div>
        </div>
      )}
      {deletePrice && (
        <div className="modal-overlay" onClick={() => setDeletePrice(null)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="card-title"><strong>删除模型</strong><button className="button button-ghost" onClick={() => setDeletePrice(null)}>×</button></div>
            <div className="notice notice-danger">确定删除 {deletePrice.model} 吗？这会同时移除对应的模型连接记录，操作不可恢复。</div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button className="button button-secondary" onClick={() => setDeletePrice(null)}>取消</button>
              <button className="button button-danger" onClick={async () => { await remove(`pricing/${encodeURIComponent(deletePrice.model)}`, loadAll); setDeletePrice(null); }}>确认删除</button>
            </div>
          </div>
        </div>
      )}
      {editMultiplier && (
        <div className="modal-overlay" onClick={() => setEditMultiplier(null)}>
          <div className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="card-title">
              <strong>峰谷倍数 · {editMultiplier.model}</strong>
              <button className="button button-ghost" onClick={() => setEditMultiplier(null)}>×</button>
            </div>
            <div className="tab-bar" style={{ marginTop: 6 }}>
              {(multiplierDays.length ? multiplierDays : [editMultiplier]).map((row) => (
                <button
                  key={row.business_date}
                  className={`chip${multiplierDate === row.business_date ? " active" : ""}`}
                  onClick={() => { setMultiplierDate(row.business_date); setEditMultiplier(multiplierDays.find((item) => item.business_date === row.business_date) || row); }}
                >
                  {row.business_date}
                </button>
              ))}
            </div>
            <div className="stat-mini" style={{ marginBottom: 15 }}>日期 + 每小时计费倍数，未来两天可调整。</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
              {(editMultiplier.hourly_multipliers || []).map((value, hour) => (
                <div key={hour}>
                  <label className="label">{editMultiplier.business_date.replace("-", "/").slice(5)} {String(hour).padStart(2, "0")}:00</label>
                  <input
                    className="input"
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={value}
                    onChange={(event) => {
                      const next = [...(editMultiplier.hourly_multipliers || [])];
                      next[hour] = Number(event.target.value || 0);
                      setEditMultiplier({ ...editMultiplier, hourly_multipliers: next });
                    }}
                  />
                </div>
              ))}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
              <button className="button button-secondary" onClick={() => setEditMultiplier(null)}>取消</button>
              <button className="button button-primary" onClick={saveMultiplier}>保存曲线</button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
