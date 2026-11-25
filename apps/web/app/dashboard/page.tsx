"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Doughnut, Line } from "react-chartjs-2";
import { useRouter } from "next/navigation";
import AppShell from "../components/AppShell";

interface UsageSummary { requests: number; input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_write_tokens: number; cost: number; }
interface ModelDistributionItem { model: string; requests: number; tokens: number; cost: number; }
interface TrendItem { date: string; requests: number; input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_write_tokens: number; cost: number; }
interface RecentUsageItem { id: number; model: string; input_tokens: number; output_tokens: number; cache_read_tokens: number; cache_write_tokens: number; tokens: number; cost: number; created_at: string; }
interface DashboardData {
  range_days: number;
  currency: string;
  balance: { available: number; reserved: number; currency: string };
  today: UsageSummary;
  range: UsageSummary;
  total: UsageSummary;
  active_api_keys: number;
  total_api_keys: number;
  model_distribution: ModelDistributionItem[];
  trend: TrendItem[];
  recent_usage: RecentUsageItem[];
}

const API = "https://api.vemixapp.com";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Tooltip,
  Legend,
);

function formatTokens(value: number) {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<"today" | "week" | "month">("today");
  const [refreshToken, setRefreshToken] = useState(0);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [now, setNow] = useState(new Date());
  const router = useRouter();

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    setEmail(localStorage.getItem("email") || "用户");
    setLoading(true);
    setError("");
    const days = range === "today" ? 1 : range === "week" ? 7 : 30;
    const granularity = range === "today" ? "hour" : "day";
    fetch(`${API}/me/dashboard?days=${days}&granularity=${granularity}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (response) => {
        if (response.status === 401) { router.push("/login"); return; }
        if (!response.ok) { setError("无法加载仪表盘数据"); return; }
        setDashboard(await response.json());
      })
      .catch(() => setError("无法连接服务"))
      .finally(() => setLoading(false));
  }, [range, refreshToken, router]);

  const displayName = useMemo(() => {
    const value = (email || "用户").split("@")[0];
    return value.length > 32 ? `${value.slice(0, 32)}…` : value;
  }, [email]);

  const greeting = now.getHours() < 12 ? "早上好" : now.getHours() < 18 ? "下午好" : "晚上好";
  const currency = dashboard?.currency || "MYR";
  const todayTokens = dashboard ? dashboard.today.input_tokens + dashboard.today.output_tokens : 0;
  const totalTokens = dashboard ? dashboard.total.input_tokens + dashboard.total.output_tokens : 0;

  const donutData = useMemo(() => {
    if (!dashboard || !dashboard.model_distribution.length) return null;
    const labels = dashboard.model_distribution.map((item) => item.model);
    const values = dashboard.model_distribution.map((item) => item.tokens);
    const colors = labels.map((_, index) => `hsl(${210 + index * 36} 72% 62%)`);
    return {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderColor: "#ffffff",
        borderWidth: 2,
        cutout: "68%",
      }],
    };
  }, [dashboard]);

  const chartData = useMemo(() => {
    if (!dashboard) return null;
    const points = dashboard.trend.map((item) => ({
      date: item.date,
      input: item.input_tokens,
      output: item.output_tokens,
      cacheWrite: item.cache_write_tokens,
      cacheRead: item.cache_read_tokens,
    }));
    return {
      labels: points.map((point) => range === "today" ? point.date.slice(11, 16) : point.date),
      datasets: [
        { label: "输入", data: points.map((point) => point.input), borderColor: "#6b7d5a", borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0, fill: false },
        { label: "输出", data: points.map((point) => point.output), borderColor: "#4a9d8b", borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0, fill: false },
        { label: "缓存创建", data: points.map((point) => point.cacheWrite), borderColor: "#b08968", borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0, fill: false },
        { label: "缓存读取", data: points.map((point) => point.cacheRead), borderColor: "#82956f", borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, tension: 0, fill: false },
      ],
    };
  }, [dashboard, range]);

  const statCard = (label: string, value: string, sub: string) => (
    <div className="card"><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="stat-mini">{sub}</div></div>
  );

  return (
    <AppShell active="/dashboard" email={email} title="仪表盘" subtitle="余额、用量、模型分布和快捷操作">
      {error && <div className="notice notice-danger" style={{ marginBottom: 16 }}>{error}</div>}
      <div className="card dashboard-hero" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
          <div>
            <div className="stat-mini">Nova API · 稳定、高效、开放，让 AI 更简单</div>
            <h1 style={{ margin: "8px 0 6px", fontSize: 30, lineHeight: 1.2 }}>{displayName}，{greeting}！</h1>
            <div className="stat-mini">现在是：{now.toLocaleString("zh-CN")}</div>
            <div className="stat-mini" style={{ marginTop: 4 }}>选择分组后，接入 Codex / Claude Code 时仍需明确输入模型 ID。</div>
            <Link className="button button-primary" style={{ marginTop: 16 }} href="/models">去模型广场选择 →</Link>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <select className="select" value={range} onChange={(event) => setRange(event.target.value as "today" | "week" | "month")}>
              <option value="today">今天</option>
              <option value="week">本周</option>
              <option value="month">本月</option>
            </select>
            <button className="button button-secondary" onClick={() => setRefreshToken((value) => value + 1)}>刷新</button>
          </div>
        </div>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        {statCard("余额", `${currency} ${(dashboard?.balance.available ?? 0).toFixed(2)}`, "可用")}
        {statCard("API 密钥", String(dashboard?.active_api_keys ?? 0), `${dashboard?.total_api_keys ?? 0} 个密钥`)}
        {statCard("今日请求", String(dashboard?.today.requests ?? 0), `累计 ${dashboard?.total.requests ?? 0} 次`)}
        {statCard("今日消费", `${currency} ${(dashboard?.today.cost ?? 0).toFixed(2)}`, `累计 ${currency} ${(dashboard?.total.cost ?? 0).toFixed(2)}`)}
      </div>

      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        {statCard("今日 Token", formatTokens(todayTokens), `输入 ${formatTokens(dashboard?.today.input_tokens ?? 0)} · 输出 ${formatTokens(dashboard?.today.output_tokens ?? 0)} · 缓存 ${formatTokens((dashboard?.today.cache_read_tokens ?? 0) + (dashboard?.today.cache_write_tokens ?? 0))}`)}
        {statCard("累计 Token", formatTokens(totalTokens), `输入 ${formatTokens(dashboard?.total.input_tokens ?? 0)} · 输出 ${formatTokens(dashboard?.total.output_tokens ?? 0)} · 缓存 ${formatTokens((dashboard?.total.cache_read_tokens ?? 0) + (dashboard?.total.cache_write_tokens ?? 0))}`)}
        {statCard("范围请求", String(dashboard?.range.requests ?? 0), range === "today" ? "今天真实数据" : range === "week" ? "本周真实数据" : "本月真实数据")}
        {statCard("范围消费", `${currency} ${(dashboard?.range.cost ?? 0).toFixed(2)}`, range === "today" ? "今天统计" : range === "week" ? "本周统计" : "本月统计")}
      </div>

      <div className="grid grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title"><h2 className="section-title">模型分布</h2><span className="stat-mini">{range} 天</span></div>
          {dashboard && dashboard.model_distribution.length > 0 ? (
            <div style={{ display: "grid", gridTemplateColumns: "230px 1fr", gap: 18, alignItems: "center" }}>
              <div style={{ height: 230, position: "relative" }}>
                <Doughnut data={donutData} options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  cutout: "68%",
                  plugins: { legend: { display: false } },
                }} />
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead><tr><th>模型</th><th>请求</th><th>Token</th><th>消费</th></tr></thead>
                  <tbody>
                    {dashboard.model_distribution.map((item) => (
                      <tr key={item.model}><td><strong>{item.model}</strong></td><td>{item.requests.toLocaleString()}</td><td>{formatTokens(item.tokens)}</td><td>{currency} {item.cost.toFixed(2)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : <div className="empty">所选时间范围内没有用量。</div>}
        </div>

        <div className="card">
          <div className="card-title" style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
              <h2 className="section-title" style={{ margin: 0 }}>Token 使用趋势</h2>
              <span className="stat-mini">{range === "today" ? "今天" : range === "week" ? "本周" : "本月"}</span>
            </div>
            <div className="stat-mini">Chart.js 插值模式</div>
          </div>
          {chartData && dashboard && chartData.labels.length ? (
            <div style={{ height: 300, position: "relative" }}>
              <Line data={chartData} options={{
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                scales: {
                  x: {
                    title: { display: true, text: "时间" },
                    ticks: { maxRotation: 60, minRotation: 45, font: { size: 10 } },
                    grid: { display: false },
                  },
                  y: {
                    title: { display: true, text: "Token" },
                    beginAtZero: true,
                    ticks: { callback: (value) => formatTokens(Number(value)) },
                    grid: { color: "rgba(0,0,0,.06)" },
                  },
                },
                plugins: { legend: { position: "top", labels: { boxWidth: 10 } } },
              }} />
            </div>
          ) : <div className="empty">所选时间范围内没有趋势数据。</div>}
        </div>
      </div>

      <div className="card">
        <div className="card">
          <div className="card-title"><h2 className="section-title">最近使用</h2><span className="stat-mini">{range} 天</span></div>
          {dashboard?.recent_usage.length === 0 && <div className="empty">还没有用量记录。</div>}
          <div style={{ display: "grid", gap: 10 }}>
            {dashboard?.recent_usage.map((item) => (
              <div key={item.id} className="notice" style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
                <div>
                  <strong>{item.model}</strong>
                  <div className="stat-mini">{new Date(item.created_at).toLocaleString("zh-CN")}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div>{currency} {item.cost.toFixed(2)}</div>
                  <div className="stat-mini">{item.tokens.toLocaleString()} tokens</div>
                  {((item.cache_read_tokens || 0) > 0 || (item.cache_write_tokens || 0) > 0) && (
                    <div className="stat-mini">缓存读取 {formatTokens(item.cache_read_tokens || 0)} · 缓存写入 {formatTokens(item.cache_write_tokens || 0)}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
          {dashboard && dashboard.recent_usage.length > 0 && (
            <div style={{ textAlign: "center", marginTop: 18 }}>
              <Link className="button button-ghost" style={{ padding: 0 }} href="/usage">查看全部 →</Link>
            </div>
          )}
        </div>

      </div>

      {loading && <div className="empty">加载真实数据中…</div>}
    </AppShell>
  );
}
