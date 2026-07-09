"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import {
  API_BASE,
  apiFetch,
  Asset,
  AssetDetail,
  AssetList,
  Folder,
  getToken,
  Tag,
  Task,
  AssetCleanupResult,
} from "@/lib/api";

type ViewMode = "grid" | "list";
type SortBy = "name" | "size_bytes" | "file_modified_at" | "asset_type" | "last_opened_at";

function formatSize(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function formatDate(value: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function thumbnailSrc(asset: Asset | AssetDetail) {
  if (!asset.thumbnail_url) return null;
  const apiRoot = API_BASE.replace(/\/api\/v1$/, "");
  return `${apiRoot}${asset.thumbnail_url}`;
}

export default function LibraryPage() {
  const router = useRouter();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<AssetDetail | null>(null);
  const [query, setQuery] = useState("");
  const [assetType, setAssetType] = useState("");
  const [tagId, setTagId] = useState("");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>("file_modified_at");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [folderPath, setFolderPath] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [description, setDescription] = useState("");
  const [author, setAuthor] = useState("");
  const [rating, setRating] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeTask = useMemo(
    () => tasks.find((task) => task.status === "pending" || task.status === "running"),
    [tasks],
  );

  async function loadAssets() {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (assetType) params.set("type", assetType);
    if (tagId) params.set("tag_id", tagId);
    if (favoriteOnly) params.set("favorite", "true");
    params.set("sort_by", sortBy);
    params.set("sort_order", sortBy === "name" ? "asc" : "desc");
    const result = await apiFetch<AssetList>(`/assets?${params.toString()}`);
    setAssets(result.items);
  }

  async function loadFolders() {
    setFolders(await apiFetch<Folder[]>("/folders"));
  }

  async function loadTasks() {
    setTasks(await apiFetch<Task[]>("/tasks"));
  }

  async function loadTags() {
    setTags(await apiFetch<Tag[]>("/tags"));
  }

  async function loadAll() {
    await Promise.all([loadAssets(), loadFolders(), loadTasks(), loadTags()]);
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    void loadAll().catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  useEffect(() => {
    if (!activeTask) return;
    const timer = window.setInterval(async () => {
      await loadTasks();
      await loadAssets();
    }, 1800);
    return () => window.clearInterval(timer);
  }, [activeTask, query, assetType, tagId, favoriteOnly, sortBy]);

  useEffect(() => {
    if (!selected) return;
    setDescription(selected.description ?? "");
    setAuthor(selected.author ?? "");
    setRating(selected.rating ?? 0);
  }, [selected]);

  async function addFolder(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    try {
      const folder = await apiFetch<Folder>("/folders", {
        method: "POST",
        body: JSON.stringify({ path: folderPath }),
      });
      setFolderPath("");
      await loadFolders();
      await apiFetch<Task>(`/folders/${folder.id}/scan`, { method: "POST" });
      await loadTasks();
      setMessage("扫描任务已创建，素材列表会自动刷新。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加目录失败");
    }
  }

  async function scanFolder(folderId: string) {
    setMessage(null);
    setError(null);
    try {
      await apiFetch<Task>(`/folders/${folderId}/scan`, { method: "POST" });
      await loadTasks();
      setMessage("扫描任务已创建。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "扫描失败");
    }
  }

  async function selectAsset(asset: Asset) {
    const detail = await apiFetch<AssetDetail>(`/assets/${asset.id}`);
    setSelected(detail);
    await apiFetch(`/assets/${asset.id}/open`, { method: "POST" });
  }

  async function addTags(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    const tagNames = tagInput
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const detail = await apiFetch<AssetDetail>(`/assets/${selected.id}/tags`, {
      method: "POST",
      body: JSON.stringify({ tag_names: tagNames }),
    });
    setSelected(detail);
    setTagInput("");
    await loadTags();
    await loadAssets();
  }

  async function cleanupAssets() {
    setMessage(null);
    setError(null);
    try {
      const result = await apiFetch<AssetCleanupResult>("/assets/cleanup", { method: "POST" });
      await loadAssets();
      setMessage(
        `清理完成：排除目录 ${result.excluded_removed} 条，失效路径 ${result.missing_removed} 条。`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "清理失败");
    }
  }

  async function saveDetails() {
    if (!selected) return;
    const updated = await apiFetch<Asset>(`/assets/${selected.id}`, {
      method: "PATCH",
      body: JSON.stringify({ description, author, rating }),
    });
    setSelected({ ...selected, ...updated });
    await loadAssets();
  }

  async function toggleFavorite() {
    if (!selected) return;
    const updated = await apiFetch<Asset>(`/assets/${selected.id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_favorite: !selected.is_favorite }),
    });
    setSelected({ ...selected, ...updated });
    await loadAssets();
  }

  return (
    <AppShell>
      <div className="section-title">
        <h1>素材库</h1>
        <button className="button secondary" onClick={() => void loadAll()}>
          刷新
        </button>
      </div>

      <div className="toolbar">
        <input
          className="input"
          placeholder="搜索名称、路径、作者、备注"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select
          className="select"
          value={assetType}
          onChange={(event) => setAssetType(event.target.value)}
        >
          <option value="">全部类型</option>
          <option value="image">图片</option>
          <option value="video">视频</option>
          <option value="model">模型</option>
          <option value="motion">动作</option>
          <option value="ue">UE</option>
        </select>
        <select
          className="select"
          value={tagId}
          onChange={(event) => setTagId(event.target.value)}
        >
          <option value="">全部标签</option>
          {tags.map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </select>
        <select
          className="select"
          value={sortBy}
          onChange={(event) => setSortBy(event.target.value as SortBy)}
        >
          <option value="file_modified_at">修改时间</option>
          <option value="name">名称</option>
          <option value="size_bytes">大小</option>
          <option value="asset_type">类型</option>
          <option value="last_opened_at">最近打开</option>
        </select>
        <button className="button secondary" onClick={() => setFavoriteOnly((value) => !value)}>
          {favoriteOnly ? "全部素材" : "只看收藏"}
        </button>
        <button className="button secondary" onClick={() => setViewMode("grid")}>
          网格
        </button>
        <button className="button secondary" onClick={() => setViewMode("list")}>
          列表
        </button>
        <button className="button" onClick={() => void loadAssets()}>
          搜索
        </button>
        <button className="button secondary" onClick={() => void cleanupAssets()}>
          清理索引
        </button>
      </div>

      <form className="toolbar" onSubmit={addFolder}>
        <input
          className="input"
          placeholder="输入本地素材目录，例如 E:\\Assets"
          value={folderPath}
          onChange={(event) => setFolderPath(event.target.value)}
        />
        <button className="button secondary" type="submit">
          添加并扫描
        </button>
      </form>

      {message ? <p className="asset-sub">{message}</p> : null}
      {error ? <p className="asset-sub">{error}</p> : null}

      <div className="content-grid">
        <section>
          {viewMode === "grid" ? (
            <div className="grid">
              {assets.map((asset) => {
                const thumb = thumbnailSrc(asset);
                return (
                  <button className="asset-card" key={asset.id} onClick={() => selectAsset(asset)}>
                    <div className="thumb">
                      {thumb ? <img alt="" src={thumb} /> : asset.extension.toUpperCase()}
                    </div>
                    <div className="asset-meta">
                      <div className="asset-name" title={asset.name}>
                        {asset.is_favorite ? "★ " : ""}
                        {asset.name}
                      </div>
                      <div className="asset-sub">
                        {asset.asset_type} · {formatSize(asset.size_bytes)}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="table">
              <div className="table-row header">
                <span>名称</span>
                <span>类型</span>
                <span>大小</span>
                <span>修改时间</span>
              </div>
              {assets.map((asset) => (
                <button
                  className="table-button table-row"
                  key={asset.id}
                  onClick={() => selectAsset(asset)}
                >
                  <span className="asset-name">{asset.is_favorite ? "★ " : ""}{asset.name}</span>
                  <span>{asset.asset_type}</span>
                  <span>{formatSize(asset.size_bytes)}</span>
                  <span>{formatDate(asset.file_modified_at)}</span>
                </button>
              ))}
            </div>
          )}
        </section>

        <aside className="panel">
          {selected ? (
            <>
              <div className="section-title">
                <h2>{selected.name}</h2>
                <button className="button ghost" onClick={() => setSelected(null)}>
                  关闭
                </button>
              </div>
              <div className="thumb">
                {thumbnailSrc(selected) ? <img alt="" src={thumbnailSrc(selected) ?? ""} /> : selected.extension.toUpperCase()}
              </div>
              <div className="detail-actions">
                <button className="button secondary" onClick={toggleFavorite}>
                  {selected.is_favorite ? "取消收藏" : "收藏"}
                </button>
                <button className="button" onClick={saveDetails}>
                  保存详情
                </button>
              </div>
              <label className="field">
                <span className="label">评分</span>
                <select
                  className="select"
                  value={rating}
                  onChange={(event) => setRating(Number(event.target.value))}
                >
                  {[0, 1, 2, 3, 4, 5].map((value) => (
                    <option key={value} value={value}>
                      {value} 星
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="label">作者</span>
                <input
                  className="input"
                  value={author}
                  onChange={(event) => setAuthor(event.target.value)}
                />
              </label>
              <label className="field">
                <span className="label">备注</span>
                <textarea
                  className="textarea"
                  rows={4}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </label>
              <div className="field">
                <span className="label">路径</span>
                <span>{selected.path}</span>
              </div>
              <div className="field">
                <span className="label">类型</span>
                <span>
                  {selected.asset_type} / {selected.extension}
                </span>
              </div>
              <div className="field">
                <span className="label">大小</span>
                <span>{formatSize(selected.size_bytes)}</span>
              </div>
              <div className="field">
                <span className="label">标签</span>
                <div className="tag-row">
                  {selected.tags.map((tag) => (
                    <span className="tag" key={tag.id}>
                      {tag.name}
                    </span>
                  ))}
                </div>
              </div>
              <form onSubmit={addTags}>
                <label className="field">
                  <span className="label">添加标签，逗号分隔</span>
                  <input
                    className="input"
                    value={tagInput}
                    onChange={(event) => setTagInput(event.target.value)}
                  />
                </label>
                <button className="button" type="submit">
                  保存标签
                </button>
              </form>
            </>
          ) : (
            <>
              <h2>任务与目录</h2>
              {activeTask ? (
                <div className="task-item">
                  <strong>{activeTask.type}</strong>
                  <div className="asset-sub">
                    {activeTask.status} · {activeTask.progress}% · {activeTask.processed}/
                    {activeTask.total}
                  </div>
                </div>
              ) : (
                <p className="asset-sub">当前没有运行中的任务。</p>
              )}
              <div className="field">
                <span className="label">素材目录</span>
                <div className="folder-list">
                  {folders.map((folder) => (
                    <div className="folder-item" key={folder.id}>
                      <div className="asset-name">{folder.name}</div>
                      <div className="asset-sub">{folder.path}</div>
                      <div className="detail-actions">
                        <button className="button secondary" onClick={() => scanFolder(folder.id)}>
                          重新扫描
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </aside>
      </div>
    </AppShell>
  );
}
