"use client";

import { useEffect, useState } from "react";
import {
  apiFetch,
  Asset,
  AssetList,
  MissingAssetScanResult,
  TrashSummary,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";

function formatSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function formatDate(value: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

export default function MissingPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [lastScan, setLastScan] = useState<MissingAssetScanResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadMissing() {
    const result = await apiFetch<AssetList>("/assets/missing");
    setAssets(result.items);
  }

  useEffect(() => {
    void loadMissing().catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  async function scanMissing() {
    setMessage(null);
    setError(null);
    try {
      const result = await apiFetch<MissingAssetScanResult>("/assets/missing/scan", {
        method: "POST",
      });
      setLastScan(result);
      await loadMissing();
      setMessage(
        `检查 ${result.checked_count} 个素材，发现 ${result.missing_count} 个失效索引，恢复 ${result.restored_count} 个索引。`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "检查失败");
    }
  }

  async function moveToTrash(assetId: string) {
    setMessage(null);
    setError(null);
    try {
      const result = await apiFetch<TrashSummary>(`/assets/${assetId}`, { method: "DELETE" });
      await loadMissing();
      setMessage(`已移入回收站。当前回收站共有 ${result.deleted_count} 条索引。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "移入回收站失败");
    }
  }

  return (
    <AppShell>
      <div className="section-title">
        <h1>失效素材</h1>
        <div className="detail-actions">
          <button className="button secondary" onClick={() => void loadMissing()}>
            刷新
          </button>
          <button className="button" onClick={() => void scanMissing()}>
            检查文件状态
          </button>
        </div>
      </div>

      <p className="asset-sub">
        失效素材表示数据库索引仍存在，但磁盘上的原始文件已经被移动或删除。
      </p>
      {message ? <p className="asset-sub">{message}</p> : null}
      {error ? <p className="asset-sub">{error}</p> : null}

      {lastScan ? (
        <section className="stat-grid">
          <div className="stat-card">
            <div className="label">检查数量</div>
            <div className="stat-value">{lastScan.checked_count}</div>
          </div>
          <div className="stat-card">
            <div className="label">失效索引</div>
            <div className="stat-value">{lastScan.missing_count}</div>
          </div>
          <div className="stat-card">
            <div className="label">恢复索引</div>
            <div className="stat-value">{lastScan.restored_count}</div>
          </div>
        </section>
      ) : null}

      <section className="panel">
        <div className="table">
          <div className="table-row header">
            <span>名称</span>
            <span>大小</span>
            <span>失效时间</span>
            <span>操作</span>
          </div>
          {assets.map((asset) => (
            <div className="table-row" key={asset.id}>
              <span className="asset-name">{asset.name}</span>
              <span>{formatSize(asset.size_bytes)}</span>
              <span>{formatDate(asset.missing_since)}</span>
              <button className="button secondary" onClick={() => moveToTrash(asset.id)}>
                移入回收站
              </button>
            </div>
          ))}
        </div>
        {assets.length === 0 ? <p className="asset-sub">当前没有失效素材。</p> : null}
      </section>
    </AppShell>
  );
}
