"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { apiFetch, Asset, AssetList, getToken, TrashSummary } from "@/lib/api";

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

export default function TrashPage() {
  const router = useRouter();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadTrash() {
    const result = await apiFetch<AssetList>("/trash/assets");
    setAssets(result.items);
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    void loadTrash().catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [router]);

  async function restore(assetId: string) {
    setMessage(null);
    setError(null);
    try {
      await apiFetch<Asset>(`/trash/assets/${assetId}/restore`, { method: "POST" });
      await loadTrash();
      setMessage("素材索引已恢复。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "恢复失败");
    }
  }

  async function purge(assetId: string) {
    setMessage(null);
    setError(null);
    try {
      await apiFetch(`/trash/assets/${assetId}`, { method: "DELETE" });
      await loadTrash();
      setMessage("素材索引已永久删除，磁盘文件未被删除。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "永久删除失败");
    }
  }

  async function emptyTrash() {
    setMessage(null);
    setError(null);
    try {
      const result = await apiFetch<TrashSummary>("/trash/assets", { method: "DELETE" });
      await loadTrash();
      setMessage(`回收站已清空，删除 ${result.purged_count} 条索引，磁盘文件未被删除。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "清空回收站失败");
    }
  }

  return (
    <AppShell>
      <div className="section-title">
        <h1>回收站</h1>
        <div className="detail-actions">
          <button className="button secondary" onClick={() => void loadTrash()}>
            刷新
          </button>
          <button className="button secondary" onClick={() => void emptyTrash()}>
            清空回收站
          </button>
        </div>
      </div>

      <p className="asset-sub">回收站只管理数据库索引，不会删除磁盘上的原始素材文件。</p>
      {message ? <p className="asset-sub">{message}</p> : null}
      {error ? <p className="asset-sub">{error}</p> : null}

      <section className="panel">
        <div className="table">
          <div className="table-row header">
            <span>名称</span>
            <span>大小</span>
            <span>删除时间</span>
            <span>操作</span>
          </div>
          {assets.map((asset) => (
            <div className="table-row" key={asset.id}>
              <span className="asset-name">{asset.name}</span>
              <span>{formatSize(asset.size_bytes)}</span>
              <span>{formatDate(asset.deleted_at)}</span>
              <span className="detail-actions">
                <button className="button secondary" onClick={() => restore(asset.id)}>
                  恢复
                </button>
                <button className="button secondary" onClick={() => purge(asset.id)}>
                  永久删除索引
                </button>
              </span>
            </div>
          ))}
        </div>
        {assets.length === 0 ? <p className="asset-sub">回收站为空。</p> : null}
      </section>
    </AppShell>
  );
}
