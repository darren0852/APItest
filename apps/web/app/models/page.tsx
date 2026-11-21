"use client";

import { useEffect, useMemo, useState } from "react";
import AppShell from "../components/AppShell";

interface PublicModel {
  model: string;
  input_sell: number;
  output_sell: number;
  cache_write_sell: number;
  cache_read_sell: number;
  official?: [number, number, number, number] | null;
  peak_multiplier?: number;
}

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

interface PublicGroup {
  group_name: string;
  models: PublicModel[];
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function formatRM(value: number | undefined, fallback = "—") {
  if (typeof value !== "number" && typeof value !== "string") return fallback;
  return `RM ${(Number(value) || 0).toFixed(2)}`;
}

function SparkLine({ multiplier }: { multiplier: number }) {
  const points = Array.from({ length: 24 }, (_, i) => {
    const wave = Math.sin((i / 24) * Math.PI * 2) * 0.06;
    return multiplier + wave + ((i * 13) % 7) * 0.004;
  });
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const coords = points.map((value, index) => `${(index / 23) * 72},${26 - ((value - min) / range) * 20}`).join(" ");
  return (
    <svg width="72" height="28" className="sparkline">
      <polyline points={coords} fill="none" stroke="#B7B89F" strokeWidth="1.5" />
    </svg>
  );
}

interface DetailData {
  ranges: { label: string; series: number[] }[];
}

function MultiplierModal({ model, onClose }: { model: string; onClose: () => void }) {
  const [data, setData] = useState<DetailData | null>(null);
  const [range, setRange] = useState("1D");
  useEffect(() => {
    fetch(`${API}/public/model-multiplier-history/${encodeURIComponent(model)}`)
      .then((response) => response.json())
      .then(setData)
      .catch(() => setData(null));
  }, [model]);
  const active = data?.ranges.find((item) => item.label === range);
  const series = active?.series || [];
  const min = Math.min(...series, 1);
  const max = Math.max(...series, 1.01);
  const pad = (max - min) * 0.15 || 0.1;
  const lo = min - pad;
  const hi = max + pad;
  const width = 560;
  const height = 220;
  const coords = series.map((value, index) => `${(index / Math.max(series.length - 1, 1)) * width},${height - ((value - lo) / (hi - lo)) * height}`).join(" ");
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h3 className="section-title">{model}</h3>
            <span className="stat-mini">高峰/低峰倍数走势</span>
          </div>
          <button className="btn btn-ghost" onClick={onClose}>关闭</button>
        </div>
        <div className="tab-bar" style={{ margin: "14px 0" }}>
          {(data?.ranges || []).map((item) => (
            <button key={item.label} className={`chip${range === item.label ? " active" : ""}`} onClick={() => setRange(item.label)}>{item.label}</button>
          ))}
        </div>
        {series.length > 0 ? (
          <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="multiplier-chart">
            <polyline points={coords} fill="none" stroke="#777C6D" strokeWidth="2" />
          </svg>
        ) : (
          <div className="empty">加载中…</div>
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
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailModel, setDetailModel] = useState("");

  useEffect(() => {
    fetch(`${API}/public/models`)
      .then((response) => response.json())
      .then((payload: PublicGroup[]) => {
        setData(payload);
        setSelectedGroup(payload[0]?.group_name || "");
      })
      .catch(() => setError("无法加载模型数据"))
      .finally(() => setLoading(false));
  }, []);

  const rows = useMemo(() => {
    const models = data.find((group) => group.group_name === selectedGroup)?.models || [];
    return [...models].sort((a, b) => a.model.localeCompare(b.model)).filter((model) => !search || model.model.toLowerCase().includes(search.toLowerCase()));
  }, [data, selectedGroup, search]);

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
            onClick={() => { setSelectedGroup(group.group_name); setSearch(""); }}
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

        <input
          className="input"
          placeholder="搜索模型 ID…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />

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
                  <td><SparkLine multiplier={row.peak_multiplier || 1} /></td>
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
