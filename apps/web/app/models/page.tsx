"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Line } from "react-chartjs-2";
import AppShell from "../components/AppShell";
import {
  PublicModelCacheGroup,
  PublicModelCacheItem,
  readCachedPublicModels,
  prefetchPublicModels,
  startPublicModelsRefresh,
} from "../../lib/public-models";

type PublicModel = PublicModelCacheItem;

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

const MODEL_FEATURES: Record<string, number[]> = {
  "glm-5.3": [1, 2],
  "glm-5.2": [1, 2],
  "glm-5.3-flash": [1, 2, 3],
  "kimi-k3.1-pro-highspeed": [1, 2, 3],
  "kimi-k3": [1, 2, 3],
  "kimi-k3.1-pro": [1, 2, 3],
  "kimi-k2.7-code": [1, 2, 3],
  "kimi-k2.6": [1, 2, 3],
  "MiniMax-M3": [1, 2, 3],
  "MiniMax-M3.1-Flash": [1, 2, 3, 4, 5],
  "deepseek-v4-pro:0813": [1, 2],
  "deepseek-v4-pro": [1, 2, 5],
  "deepseek-v4.1-flash": [1, 2, 3],
  "deepseek-v4-flash:0731": [1, 2],
  "deepseek-v4-flash": [1, 2, 5],
};

const FEATURE_META: Record<number, { label: string; icon: string }> = {
  1: { label: "文本推理", icon: "💬" },
  2: { label: "工具调用", icon: "🛠" },
  3: { label: "视觉", icon: "👁" },
  4: { label: "PDF 输入", icon: "📄" },
  5: { label: "联网搜索", icon: "🌐" },
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="copy-btn"
      title="复制模型 ID"
      onClick={async (event) => {
        event.stopPropagation();
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        } catch {}
      }}
    >
      {copied ? "✓" : "⧉"}
    </button>
  );
}

type PublicGroup = PublicModelCacheGroup;

const API = "https://api.vemixapp.com";

function formatRM(value: number | undefined, fallback = "—") {
  if (typeof value !== "number" && typeof value !== "string") return fallback;
  return `RM ${(Number(value) || 0).toFixed(2)}`;
}

const MULTIPLIER_CACHE_KEY = "public-multipliers-cache-v2";
const MULTIPLIER_CACHE_TTL = 60_000;

interface DetailData {
  ranges: { label: string; series: number[] }[];
  hours: string[];
  current_multiplier: number;
  series?: number[];
}

function SparkLine({ series }: { series: number[] }) {
  const points = series.length === 24 ? series : Array.from({ length: 24 }, () => 1);
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const coords = points.map((value, index) => `${(index / 23) * 72},${26 - ((value - min) / range) * 20}`).join(" ");
  return (
    <svg width="72" height="28" className="sparkline">
      <polyline points={coords} fill="none" stroke="var(--accent-2)" strokeWidth="1.5" />
    </svg>
  );
}

function readCachedMultiplier(model: string): DetailData | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(MULTIPLIER_CACHE_KEY);
    const payload = raw ? JSON.parse(raw) as Record<string, { saved_at: number; data: DetailData }> : {};
    const cached = payload[model];
    return cached && Date.now() - cached.saved_at < MULTIPLIER_CACHE_TTL ? cached.data : null;
  } catch {
    return null;
  }
}

function cacheMultiplier(model: string, data: DetailData): void {
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(MULTIPLIER_CACHE_KEY);
    const payload = raw ? JSON.parse(raw) as Record<string, { saved_at: number; data: DetailData }> : {};
    payload[model] = { saved_at: Date.now(), data };
    localStorage.setItem(MULTIPLIER_CACHE_KEY, JSON.stringify(payload));
  } catch {}
}

function MultiplierModal({ model, onClose }: { model: string; onClose: () => void }) {
  const [data, setData] = useState<DetailData | null>(null);
  useEffect(() => {
    const cached = readCachedMultiplier(model);
    if (cached) { setData(cached); return; }
    fetch(`${API}/public/model-multiplier-history/${encodeURIComponent(model)}`)
      .then((response) => response.json())
      .then((payload) => {
        cacheMultiplier(model, payload);
        return payload;
      })
      .then(setData)
      .catch(() => setData(null));
  }, [model]);
  const series = data?.ranges?.[0]?.series || data?.series || [];
  const min = series.length ? Math.min(...series) : 1;
  const max = series.length ? Math.max(...series) : 1;
  const chartData = {
    labels: data?.hours || [],
    datasets: [{
      label: "计费倍数",
      data: series,
      borderColor: "#465fff",
      backgroundColor: "rgba(70,95,255,.12)",
      borderWidth: 2,
      pointBackgroundColor: "#465fff",
      pointBorderColor: "#ffffff",
      pointBorderWidth: 2,
      pointRadius: 4,
      pointHoverRadius: 6,
      tension: 0,
      fill: false,
    }],
  };
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h3 className="section-title">{model}</h3>
            <span className="stat-mini">真实计费倍数 · 当前 {data?.current_multiplier?.toFixed(2) ?? "—"}×</span>
          </div>
          <button className="btn btn-ghost" onClick={onClose}>关闭</button>
        </div>
        {series.length > 0 ? (
          <div style={{ height: 280, position: "relative" }}>
            <Line data={chartData} options={{
              responsive: true,
              maintainAspectRatio: false,
              scales: {
                x: {
                  title: { display: true, text: "时间" },
                  ticks: { maxRotation: 60, minRotation: 45, font: { size: 10 } },
                  grid: { display: false },
                },
                y: {
                  title: { display: true, text: "计费倍数" },
                  beginAtZero: false,
                  ticks: { callback: (value) => `${Number(value).toFixed(2)}` },
                  grid: { color: "rgba(0,0,0,.06)" },
                },
              },
              plugins: {
                legend: { display: false },
                tooltip: {
                  callbacks: { label: (context) => `${context.parsed.y.toFixed(2)}×` },
                },
              },
            }} />
          </div>
        ) : (
          <div className="empty">加载中…</div>
        )}
        {series.length === 24 && data && (
          <div className="table-wrap" style={{ marginTop: 10 }}>
            <table className="data-table">
              <thead><tr><th>时间</th><th className="num">计费倍数</th><th>时间</th><th className="num">计费倍数</th></tr></thead>
              <tbody>
                {Array.from({ length: 12 }, (_, index) => {
                  const first = index * 2;
                  const second = first + 1;
                  return (
                    <tr key={index}>
                      <td>{data.hours[first]}</td><td className="num">{series[first].toFixed(2)}×</td>
                      <td>{data.hours[second]}</td><td className="num">{series[second].toFixed(2)}×</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="legend-row">
          <span className="stat-mini">当前倍数区间 {min.toFixed(2)}× – {max.toFixed(2)}×（平峰 = 1.00×）</span>
        </div>
      </div>
    </div>
  );
}

export default function ModelsPage() {
  const [data, setData] = useState<PublicGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailModel, setDetailModel] = useState("");

  useEffect(() => {
    let active = true;
    const cached = readCachedPublicModels();
    if (cached) {
      setData(cached);
      setSelectedGroup(cached[0]?.group_name || "");
      setLoading(false);
      startPublicModelsRefresh();
    } else {
      setLoading(true);
      prefetchPublicModels()
        .then((payload) => {
          if (!active) return;
          setData(payload);
          setSelectedGroup(payload[0]?.group_name || "");
        })
        .catch(() => {
          if (active) setError("无法加载模型数据");
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }
    return () => {
      active = false;
    };
  }, []);

  const rows = useMemo(() => {
    const models = data.find((group) => group.group_name === selectedGroup)?.models || [];
    return [...models].sort((a, b) => a.model.localeCompare(b.model));
  }, [data, selectedGroup]);

  if (error) {
    return <AppShell active="/models" title="模型广场" subtitle="供应商模型">
      <div className="notice notice-danger">{error}</div>
    </AppShell>;
  }

  if (loading) {
    return <AppShell active="/models" title="模型广场" subtitle="正在加载模型数据">
      <div className="card empty">加载中…</div>
    </AppShell>;
  }

  return (
    <AppShell active="/models" title="模型广场" subtitle="按后台分组的模型列表">
      <div className="tab-bar" style={{ marginBottom: 16 }}>
        {data.map((group) => (
          <button
            key={group.group_name}
            className={`chip${selectedGroup === group.group_name ? " active" : ""}`}
            onClick={() => setSelectedGroup(group.group_name)}
          >
            {group.group_name} · {group.models.length}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-title">
          <h2 className="section-title">{selectedGroup || "未选择分组"}</h2>
          <span className="stat-mini">{rows.length} 个模型</span>
        </div>

        <div className="table-wrap" style={{ marginTop: 14 }}>
          <table className="model-table">
            <thead>
              <tr>
                <th>模型 ID</th>
                <th>峰谷走势</th>
                <th className="num">输入</th>
                <th className="num">输出</th>
                <th className="num">缓存创建</th>
                <th className="num">缓存读取</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.model} className="model-row" onClick={() => setDetailModel(row.model)}>
                  <td>
                    <div className="model-cell">
                      <div className="model-name-row">
                        <span className="model-id">{row.model}</span>
                        <CopyButton text={row.model} />
                      </div>
                      <div className="feature-row">
                        {(MODEL_FEATURES[row.model] || []).map((feature) => (
                          <span key={feature} className="feature-tag" title={FEATURE_META[feature]?.label}>
                            {FEATURE_META[feature]?.icon} {FEATURE_META[feature]?.label}
                          </span>
                        ))}
                      </div>
                    </div>
                  </td>
                  <td><SparkLine series={row.hourly_multipliers || []} /></td>
                  <td className="num">
                    <div className="price-stack">
                      <span className="model-price">{formatRM(row.input_sell)}</span>
                      {row.official && row.official[0] > row.input_sell && (
                        <span className="official-strike">官方 {formatRM(row.official[0])}</span>
                      )}
                    </div>
                  </td>
                  <td className="num">
                    <div className="price-stack">
                      <span className="model-price">{formatRM(row.output_sell)}</span>
                      {row.official && row.official[1] > row.output_sell && (
                        <span className="official-strike">官方 {formatRM(row.official[1])}</span>
                      )}
                    </div>
                  </td>
                  <td className="num">{formatRM(row.cache_write_sell)}</td>
                  <td className="num">{formatRM(row.cache_read_sell)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {rows.length === 0 && <div className="empty">这个组别还没有模型。</div>}
      </div>
      {detailModel && <MultiplierModal model={detailModel} onClose={() => setDetailModel("")} />}
    </AppShell>
  );
}
