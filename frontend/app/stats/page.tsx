"use client";

import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, StatsOverview } from "@/lib/api";

function formatSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  if (value < 1024 * 1024 * 1024 * 1024) return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
  return `${(value / 1024 / 1024 / 1024 / 1024).toFixed(1)} TB`;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

export default function StatsPage() {
  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<StatsOverview>("/stats/overview")
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : "加载统计失败"));
  }, []);

  const maxTypeCount = useMemo(
    () => Math.max(...(stats?.type_stats.map((item) => item.count) ?? [1])),
    [stats],
  );
  const maxExtensionCount = useMemo(
    () => Math.max(...(stats?.top_extensions.map((item) => item.count) ?? [1])),
    [stats],
  );

  return (
    <AppShell>
      <div className="section-title">
        <h1>统计</h1>
        <button
          className="button secondary"
          onClick={() => void apiFetch<StatsOverview>("/stats/overview").then(setStats)}
        >
          刷新
        </button>
      </div>

      {error ? <p className="asset-sub">{error}</p> : null}
      {!stats ? <p className="asset-sub">正在加载统计数据。</p> : null}

      {stats ? (
        <>
          <section className="stat-grid">
            <div className="stat-card">
              <div className="label">总素材</div>
              <div className="stat-value">{formatNumber(stats.total_assets)}</div>
            </div>
            <div className="stat-card">
              <div className="label">总容量</div>
              <div className="stat-value">{formatSize(stats.total_size_bytes)}</div>
            </div>
            <div className="stat-card">
              <div className="label">收藏</div>
              <div className="stat-value">{formatNumber(stats.favorite_count)}</div>
            </div>
            <div className="stat-card">
              <div className="label">标签</div>
              <div className="stat-value">{formatNumber(stats.tag_count)}</div>
            </div>
            <div className="stat-card">
              <div className="label">素材目录</div>
              <div className="stat-value">{formatNumber(stats.folder_count)}</div>
            </div>
            <div className="stat-card">
              <div className="label">近 7 天新增</div>
              <div className="stat-value">{formatNumber(stats.recent_assets_7d)}</div>
            </div>
          </section>

          <div className="content-grid">
            <section className="panel">
              <h2>类型分布</h2>
              <div className="chart-list">
                {stats.type_stats.map((item) => (
                  <div className="chart-row" key={item.asset_type}>
                    <div className="chart-row-head">
                      <strong>{item.asset_type}</strong>
                      <span>
                        {formatNumber(item.count)} · {formatSize(item.size_bytes)}
                      </span>
                    </div>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{ width: `${Math.max((item.count / maxTypeCount) * 100, 2)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <aside className="panel">
              <h2>常见扩展名</h2>
              <div className="chart-list">
                {stats.top_extensions.map((item) => (
                  <div className="chart-row" key={item.extension}>
                    <div className="chart-row-head">
                      <strong>.{item.extension}</strong>
                      <span>{formatNumber(item.count)}</span>
                    </div>
                    <div className="bar-track">
                      <div
                        className="bar-fill"
                        style={{
                          width: `${Math.max((item.count / maxExtensionCount) * 100, 2)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </aside>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}
