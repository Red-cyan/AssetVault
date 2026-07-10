"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, DuplicateAssetResponse } from "@/lib/api";

function formatSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

export default function DuplicatesPage() {
  const [data, setData] = useState<DuplicateAssetResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadDuplicates() {
    setLoading(true);
    setError(null);
    try {
      setData(await apiFetch<DuplicateAssetResponse>("/assets/duplicates"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "重复检测失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDuplicates();
  }, []);

  return (
    <AppShell>
      <div className="section-title">
        <h1>重复检测</h1>
        <button className="button secondary" onClick={() => void loadDuplicates()}>
          重新检测
        </button>
      </div>

      {loading ? <p className="asset-sub">正在计算文件指纹并检测重复素材。</p> : null}
      {error ? <p className="asset-sub">{error}</p> : null}

      {data ? (
        <>
          <section className="stat-grid">
            <div className="stat-card">
              <div className="label">重复组</div>
              <div className="stat-value">{data.total_groups}</div>
            </div>
            <div className="stat-card">
              <div className="label">重复素材</div>
              <div className="stat-value">{data.total_assets}</div>
            </div>
            <div className="stat-card">
              <div className="label">已计算指纹</div>
              <div className="stat-value">{data.hashed_assets}</div>
            </div>
          </section>

          <div className="stack">
            {data.groups.map((group) => (
              <section className="panel" key={group.file_hash}>
                <div className="section-title">
                  <h2>{group.count} 个重复素材</h2>
                  <span className="asset-sub">{formatSize(group.size_bytes)}</span>
                </div>
                <div className="table">
                  <div className="table-row header">
                    <span>名称</span>
                    <span>类型</span>
                    <span>大小</span>
                    <span>路径</span>
                  </div>
                  {group.items.map((asset) => (
                    <div className="table-row" key={asset.id}>
                      <span className="asset-name">{asset.name}</span>
                      <span>{asset.asset_type}</span>
                      <span>{formatSize(asset.size_bytes)}</span>
                      <span className="asset-sub">{asset.path}</span>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>

          {data.groups.length === 0 ? (
            <section className="panel">
              <h2>未发现重复素材</h2>
              <p className="asset-sub">当前已计算指纹的素材中没有发现重复文件。</p>
            </section>
          ) : null}
        </>
      ) : null}
    </AppShell>
  );
}
