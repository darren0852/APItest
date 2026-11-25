"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
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

  const donutAngles = useMemo(() => {
    if (!dashboard || !dashboard.model_distribution.length) return [];
    const total = dashboard.model_distribution.reduce((sum, item) => sum + item.tokens, 0) || 1;
    let cursor = 0;
    return dashboard.model_distribution.map((item, index) => {
      const ratio = item.tokens / total;
      const start = cursor * 360;
      cursor += ratio;
      return { ...item, start, ratio, color: `hsl(${210 + index * 36} 72% 62%)` };
    });
  }, [dashboard]);

  const chart = useMemo(() => {
    if (!dashboard) return null;
    const points = dashboard.trend.map((item) => ({
      date: item.date,
      input: item.input_tokens,
      output: item.output_tokens,
      cacheWrite: item.cache_write_tokens,
      cacheRead: item.cache_read_tokens,
    }));
    const max = Math.max(...points.flatMap((point) => [point.input, point.output, point.cacheWrite, point.cacheRead]), 1);
    const width = 720;
    const height = 220;
    const x = (index: number) => 42 + (points.length <= 1 ? 0 : (index * (width - 84)) / (points.length - 1));
    const y = (value: number) => height - 28 - (value / max) * (height - 56);
    const toPath = (key: "input" | "output" | "cacheWrite" | "cacheRead") => points.map((point, index) => `${index === 0 ? "M" : "L"} ${x(index).toFixed(1)} ${y(point[key]).toFixed(1)}`).join(" ");
    return { width, height, max, x, y, points, paths: { input: toPath("input"), output: toPath("output"), cacheWrite: toPath("cacheWrite"), cacheRead: toPath("cacheRead") } };
  }, [dashboard]);

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
            <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 18, alignItems: "center" }}>
              <svg viewBox="0 0 200 200" width={180} height={180}>
                <circle cx="100" cy="100" r="72" fill="none" stroke="rgba(148,163,184,.18)" strokeWidth="32" />
                {donutAngles.map((item) => (
                  <circle
                    key={item.model}
                    cx="100" cy="100" r="72"
                    fill="none"
                    stroke={item.color}
                    strokeWidth="32"
                    strokeDasharray={`${Math.max(item.ratio, 0) * 452} 452`}
                    strokeLinecap="round"
                    transform={`rotate(${item.start - 90} 100 100)`}
                  />
                ))}
              </svg>
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
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
              {[
                ["输入", "#6b7d5a", chart?.paths.input],
                ["输出", "#4a9d8b", chart?.paths.output],
                ["缓存创建", "#b08968", chart?.paths.cacheWrite],
                ["缓存读取", "#82956f", chart?.paths.cacheRead],
              ].map(([label, color, path]) => (
                <span key={label as string} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "#6b7367" }}>
                  <span style={{ width: 8, height: 8, borderRadius: 99, background: color as string, display: "inline-block" }} />
                  {label as string}
                </span>
              ))}
            </div>
          </div>
          {chart && dashboard && chart.points.some((point) => point.input + point.output + point.cacheWrite + point.cacheRead > 0) ? (
            <svg viewBox={`0 0 ${chart.width} ${chart.height}`} width="100%" height="260">
              {chart.points.some((point) => point.input + point.output + point.cacheWrite + point.cacheRead > 0) && (
                <>
                  <path d={chart.paths.input} fill="none" stroke="#6b7d5a" strokeWidth="3" strokeLinecap="round" />
                  <path d={chart.paths.output} fill="none" stroke="#4a9d8b" strokeWidth="3" strokeLinecap="round" />
                  <path d={chart.paths.cacheWrite} fill="none" stroke="#b08968" strokeWidth="3" strokeLinecap="round" />
                  <path d={chart.paths.cacheRead} fill="none" stroke="#82956f" strokeWidth="3" strokeLinecap="round" />
                </>
              )}
              {chart.points.map((point, index) => {
                const label = range === "today" ? point.date.slice(11, 16) : point.date;
                return <text key={point.date} x={chart.x(index)} y={chart.height - 8} fill="#9ba39a" fontSize={9} textAnchor="middle">{label}</text>;
              })}
              {[0, .25, .5, .75, 1].map((ratio) => (
                <g key={ratio}>
                  <line x1={42} x2={chart.width - 42} y1={chart.y(chart.max * ratio)} y2={chart.y(chart.max * ratio)} stroke="rgba(0,0,0,0.06)" strokeDasharray="3 5" />
                  <text x={8} y={chart.y(chart.max * ratio) + 3} fill="#9ba39a" fontSize={10} textAnchor="start">{formatTokens(chart.max * ratio)}</text>
                </g>
              ))}
            </svg>
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
