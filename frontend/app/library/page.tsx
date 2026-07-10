"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import {
  API_BASE,
  apiFetch,
  Asset,
  AssetDetail,
  AssetFolderGroup,
  AssetList,
  Tag,
  AssetCleanupResult,
  AssetBatchUpdateResult,
  AiAnalyzeResult,
  NaturalLanguageSearchResult,
  Project,
  TrashSummary,
} from "@/lib/api";

type ViewMode = "grid" | "list";
type SortBy = "name" | "size_bytes" | "file_modified_at" | "asset_type" | "last_opened_at";
type AssetScope = "primary" | "support" | "all";

type LibraryPreferences = {
  query: string;
  assetType: string;
  assetScope: AssetScope;
  directoryPath: string;
  tagId: string;
  favoriteOnly: boolean;
  sortBy: SortBy;
  pageSize: number;
  viewMode: ViewMode;
};

const LIBRARY_PREFERENCES_KEY = "assetvault_library_preferences";

const ROLE_OPTIONS = [
  ["character", "人物"],
  ["stage", "舞台"],
  ["motion", "动作"],
  ["music", "音乐"],
  ["texture", "贴图"],
  ["other", "其他"],
] as const;

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
  const [assets, setAssets] = useState<Asset[]>([]);
  const [folderGroups, setFolderGroups] = useState<AssetFolderGroup[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [selected, setSelected] = useState<AssetDetail | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [naturalQuery, setNaturalQuery] = useState("");
  const [assetType, setAssetType] = useState("");
  const [assetScope, setAssetScope] = useState<AssetScope>("primary");
  const [directoryPath, setDirectoryPath] = useState("");
  const [tagId, setTagId] = useState("");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [sortBy, setSortBy] = useState<SortBy>("file_modified_at");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(60);
  const [total, setTotal] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [tagInput, setTagInput] = useState("");
  const [bulkTagInput, setBulkTagInput] = useState("");
  const [bulkProjectId, setBulkProjectId] = useState("");
  const [bulkProjectRole, setBulkProjectRole] = useState("other");
  const [description, setDescription] = useState("");
  const [author, setAuthor] = useState("");
  const [rating, setRating] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preferencesReady, setPreferencesReady] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<AiAnalyzeResult | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiController, setAiController] = useState<AbortController | null>(null);

  const selectedIdSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  async function loadAssets(
    nextPage = page,
    nextPageSize = pageSize,
    overrides: Partial<LibraryPreferences> = {},
  ) {
    const nextAssetScope = overrides.assetScope ?? assetScope;
    const nextAssetType = overrides.assetType ?? assetType;
    const nextDirectoryPath = overrides.directoryPath ?? directoryPath;
    const nextQuery = overrides.query ?? query;
    const nextTagId = overrides.tagId ?? tagId;
    const nextFavoriteOnly = overrides.favoriteOnly ?? favoriteOnly;
    const nextSortBy = overrides.sortBy ?? sortBy;
    const params = new URLSearchParams();
    if (nextQuery) params.set("q", nextQuery);
    if (nextAssetType) params.set("type", nextAssetType);
    params.set("scope", nextAssetScope);
    if (nextDirectoryPath) params.set("directory_path", nextDirectoryPath);
    if (nextTagId) params.set("tag_id", nextTagId);
    if (nextFavoriteOnly) params.set("favorite", "true");
    params.set("page", String(nextPage));
    params.set("page_size", String(nextPageSize));
    params.set("sort_by", nextSortBy);
    params.set("sort_order", nextSortBy === "name" ? "asc" : "desc");
    const result = await apiFetch<AssetList>(`/assets?${params.toString()}`);
    setAssets(result.items);
    setPage(result.page);
    setPageSize(result.page_size);
    setTotal(result.total);
    setSelectedIds((ids) => ids.filter((id) => result.items.some((asset) => asset.id === id)));
  }

  async function runNaturalSearch() {
    setMessage(null);
    setError(null);
    try {
      const result = await apiFetch<NaturalLanguageSearchResult>("/search/natural-language", {
        method: "POST",
        body: JSON.stringify({ query: naturalQuery, limit: 60 }),
      });
      setAssets(result.items);
      setPage(1);
      setPageSize(60);
      setTotal(result.total);
      setMessage(
        `${result.mode === "hybrid-bge-m3" ? "BGE-M3 混合检索" : "关键词检索"}返回 ${result.total} 个候选。`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 搜索失败");
    }
  }

  async function loadFolderGroups() {
    const result = await apiFetch<AssetFolderGroup[]>("/assets/folder-groups");
    setFolderGroups(result);
    setDirectoryPath((current) =>
      current && result.some((group) => group.path === current) ? current : "",
    );
  }

  async function loadTags() {
    setTags(await apiFetch<Tag[]>("/tags"));
  }

  async function loadProjects() {
    const result = await apiFetch<Project[]>("/projects");
    setProjects(result);
    setBulkProjectId((projectId) => projectId || result[0]?.id || "");
  }

  async function loadAll() {
    await Promise.all([
      loadAssets(),
      loadFolderGroups(),
      loadTags(),
      loadProjects(),
    ]);
  }

  useEffect(() => {
    const rawPreferences = window.localStorage.getItem(LIBRARY_PREFERENCES_KEY);
    let preferences: LibraryPreferences | null = null;
    if (rawPreferences) {
      try {
        preferences = JSON.parse(rawPreferences) as LibraryPreferences;
      } catch {
        window.localStorage.removeItem(LIBRARY_PREFERENCES_KEY);
      }
    }
    if (preferences) {
      setQuery(preferences.query ?? "");
      setAssetType(preferences.assetType ?? "");
      setAssetScope(preferences.assetScope ?? "primary");
      setDirectoryPath(preferences.directoryPath ?? "");
      setTagId(preferences.tagId ?? "");
      setFavoriteOnly(Boolean(preferences.favoriteOnly));
      setSortBy(preferences.sortBy ?? "file_modified_at");
      setPageSize(preferences.pageSize ?? 60);
      setViewMode(preferences.viewMode ?? "grid");
    }
    setPreferencesReady(true);
    void Promise.all([
      loadAssets(1, preferences?.pageSize ?? 60, preferences ?? {}),
      loadFolderGroups(),
      loadTags(),
      loadProjects(),
    ]).catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  useEffect(() => {
    if (!preferencesReady) return;
    const preferences: LibraryPreferences = {
      query,
      assetType,
      assetScope,
      directoryPath,
      tagId,
      favoriteOnly,
      sortBy,
      pageSize,
      viewMode,
    };
    window.localStorage.setItem(LIBRARY_PREFERENCES_KEY, JSON.stringify(preferences));
  }, [
    preferencesReady,
    query,
    assetType,
    assetScope,
    directoryPath,
    tagId,
    favoriteOnly,
    sortBy,
    pageSize,
    viewMode,
  ]);

  useEffect(() => {
    if (!selected) return;
    setDescription(selected.description ?? "");
    setAuthor(selected.author ?? "");
    setRating(selected.rating ?? 0);
  }, [selected]);

  async function selectAsset(asset: Asset) {
    aiController?.abort();
    setAiSuggestion(null);
    const detail = await apiFetch<AssetDetail>(`/assets/${asset.id}`);
    setSelected(detail);
    await apiFetch(`/assets/${asset.id}/open`, { method: "POST" });
  }

  function toggleAssetSelection(assetId: string) {
    setSelectedIds((ids) =>
      ids.includes(assetId) ? ids.filter((id) => id !== assetId) : [...ids, assetId],
    );
  }

  function selectCurrentPage() {
    setSelectedIds(assets.map((asset) => asset.id));
  }

  async function searchFromFirstPage() {
    await loadAssets(1, pageSize);
  }

  async function changePageSize(value: number) {
    await loadAssets(1, value);
  }

  async function changeAssetScope(value: AssetScope) {
    setAssetScope(value);
    await loadAssets(1, pageSize, { assetScope: value });
  }

  async function changeAssetType(value: string) {
    setAssetType(value);
    await loadAssets(1, pageSize, { assetType: value });
  }

  async function changeDirectoryPath(value: string) {
    setDirectoryPath(value);
    await loadAssets(1, pageSize, { directoryPath: value });
  }

  async function goToPage(value: number) {
    await loadAssets(Math.min(Math.max(value, 1), totalPages), pageSize);
  }

  async function batchUpdate(
    payload: Partial<{
      is_favorite: boolean;
      tag_names: string[];
      move_to_trash: boolean;
    }>,
  ) {
    if (selectedIds.length === 0) {
      setError("请先选择素材。");
      return;
    }
    if (
      payload.move_to_trash &&
      !window.confirm(`将选中的 ${selectedIds.length} 个素材移入回收站？`)
    ) {
      return;
    }
    if (
      payload.tag_names?.length &&
      !window.confirm(`为选中的 ${selectedIds.length} 个素材添加这些标签？`)
    ) {
      return;
    }
    setMessage(null);
    setError(null);
    try {
      const result = await apiFetch<AssetBatchUpdateResult>("/assets/batch", {
        method: "PATCH",
        body: JSON.stringify({ asset_ids: selectedIds, ...payload }),
      });
      await loadTags();
      await loadAssets();
      if (payload.move_to_trash) {
        setSelected(null);
        setSelectedIds([]);
      }
      setMessage(
        `批量操作完成：匹配 ${result.matched_count} 个，更新 ${result.updated_count} 个，新增标签关联 ${result.tagged_count} 个，移入回收站 ${result.trashed_count} 个。`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量操作失败");
    }
  }

  async function batchAddTags(event: FormEvent) {
    event.preventDefault();
    const tagNames = bulkTagInput
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (tagNames.length === 0) {
      setError("请输入要添加的标签。");
      return;
    }
    await batchUpdate({ tag_names: tagNames });
    setBulkTagInput("");
  }

  async function batchAddToProject() {
    if (selectedIds.length === 0) {
      setError("请先选择素材。");
      return;
    }
    if (!bulkProjectId) {
      setError("请先创建或选择项目。");
      return;
    }
    if (!window.confirm(`将选中的 ${selectedIds.length} 个素材加入项目？`)) return;
    setMessage(null);
    setError(null);
    try {
      const detail = await apiFetch(`/projects/${bulkProjectId}/assets/batch`, {
        method: "POST",
        body: JSON.stringify({ asset_ids: selectedIds, role: bulkProjectRole }),
      });
      const projectName = projects.find((project) => project.id === bulkProjectId)?.name ?? "项目";
      setMessage(`已将 ${selectedIds.length} 个素材加入「${projectName}」。`);
      void detail;
      await loadProjects();
    } catch (err) {
      setError(err instanceof Error ? err.message : "加入项目失败");
    }
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
    if (!window.confirm("清理排除目录和失效路径的素材索引？此操作不会删除原始文件。")) return;
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

  async function analyzeAsset() {
    if (!selected) return;
    const controller = new AbortController();
    setAiController(controller);
    setAiLoading(true);
    setAiSuggestion(null);
    setMessage(null);
    setError(null);
    try {
      const result = await apiFetch<AiAnalyzeResult>(`/ai/assets/${selected.id}/analyze`, {
        method: "POST",
        signal: controller.signal,
      });
      setAiSuggestion(result);
      setMessage("分析建议已生成，确认后才会写入素材详情和标签。");
    } catch (err) {
      if (controller.signal.aborted) {
        setMessage("已取消本次分析请求。");
      } else {
        setError(err instanceof Error ? err.message : "智能分析失败");
      }
    } finally {
      setAiLoading(false);
      setAiController(null);
    }
  }

  async function applyAiSuggestion() {
    if (!selected || !aiSuggestion) return;
    setError(null);
    try {
      const result = await apiFetch<AiAnalyzeResult>(`/ai/assets/${selected.id}/apply`, {
        method: "POST",
        body: JSON.stringify({
          tags: aiSuggestion.tags,
          description: aiSuggestion.description,
          source: aiSuggestion.source,
        }),
      });
      setSelected(result.asset);
      setDescription(result.asset.description ?? "");
      setAiSuggestion(null);
      await Promise.all([loadTags(), loadAssets()]);
      setMessage(`已应用 ${result.tags.length} 个建议标签。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "应用分析建议失败");
    }
  }

  async function moveToTrash() {
    if (!selected) return;
    if (!window.confirm(`将“${selected.name}”移入回收站？`)) return;
    setMessage(null);
    setError(null);
    try {
      const result = await apiFetch<TrashSummary>(`/assets/${selected.id}`, {
        method: "DELETE",
      });
      setSelected(null);
      await loadAssets();
      setMessage(`已移入回收站。当前回收站共有 ${result.deleted_count} 条索引。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "移入回收站失败");
    }
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
          value={assetScope}
          onChange={(event) => void changeAssetScope(event.target.value as AssetScope)}
        >
          <option value="primary">主素材</option>
          <option value="support">贴图/辅助文件</option>
          <option value="all">全部索引</option>
        </select>
        <select
          className="select"
          value={assetType}
          onChange={(event) => void changeAssetType(event.target.value)}
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
        <button className="button" onClick={() => void searchFromFirstPage()}>
          搜索
        </button>
        <button className="button secondary" onClick={() => void cleanupAssets()}>
          清理索引
        </button>
      </div>

      <section className="panel folder-groups-panel">
        <div className="section-title">
          <div>
            <h2>工程目录</h2>
            <p className="asset-sub">按扫描根目录下的一级文件夹组织素材包，贴图和主文件会归到同一个工程目录。</p>
          </div>
          <button className="button secondary" onClick={() => void changeDirectoryPath("")}>
            全部工程
          </button>
        </div>
        {folderGroups.length === 0 ? (
          <p className="asset-sub">暂无工程目录。添加素材目录并扫描后会自动生成。</p>
        ) : (
          <div className="folder-group-grid">
            {folderGroups.map((group) => (
              <button
                className={`folder-group-card ${directoryPath === group.path ? "active" : ""}`}
                key={group.path}
                onClick={() => void changeDirectoryPath(group.path)}
              >
                <div className="asset-name" title={group.name}>
                  {group.name}
                </div>
                <div className="asset-sub" title={group.path}>
                  {group.path}
                </div>
                <div className="asset-sub">
                  主素材 {group.primary_count} · 辅助 {group.support_count} · 共{" "}
                  {group.total_count}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <div className="toolbar batch-toolbar">
        <span className="asset-sub">已选择 {selectedIds.length} 个素材</span>
        <button className="button secondary" onClick={selectCurrentPage}>
          选择当前页
        </button>
        <button className="button secondary" onClick={() => setSelectedIds([])}>
          清空选择
        </button>
        <button className="button secondary" onClick={() => void batchUpdate({ is_favorite: true })}>
          批量收藏
        </button>
        <button className="button secondary" onClick={() => void batchUpdate({ is_favorite: false })}>
          取消收藏
        </button>
        <button className="button secondary" onClick={() => void batchUpdate({ move_to_trash: true })}>
          移入回收站
        </button>
        <form className="inline-form" onSubmit={batchAddTags}>
          <input
            className="input"
            placeholder="批量添加标签，逗号分隔"
            value={bulkTagInput}
            onChange={(event) => setBulkTagInput(event.target.value)}
          />
          <button className="button" type="submit">
            批量打标签
          </button>
        </form>
        <div className="inline-form">
          <select
            className="select"
            value={bulkProjectId}
            onChange={(event) => setBulkProjectId(event.target.value)}
          >
            <option value="">选择项目</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
          <select
            className="select"
            value={bulkProjectRole}
            onChange={(event) => setBulkProjectRole(event.target.value)}
          >
            {ROLE_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <button className="button" onClick={() => void batchAddToProject()}>
            加入项目
          </button>
        </div>
      </div>

      <div className="toolbar">
        <input
          className="input"
          placeholder="AI 搜索：例如 找一个适合演唱会的大舞台"
          value={naturalQuery}
          onChange={(event) => setNaturalQuery(event.target.value)}
        />
        <button className="button" onClick={() => void runNaturalSearch()}>
          AI 搜索
        </button>
      </div>

      {message ? <p className="asset-sub">{message}</p> : null}
      {error ? <p className="asset-sub">{error}</p> : null}

      <div className="toolbar pagination-toolbar">
        <span className="asset-sub">
          共 {total} 个素材，第 {page} / {totalPages} 页
        </span>
        <button
          className="button secondary"
          disabled={page <= 1}
          onClick={() => void goToPage(page - 1)}
        >
          上一页
        </button>
        <button
          className="button secondary"
          disabled={page >= totalPages}
          onClick={() => void goToPage(page + 1)}
        >
          下一页
        </button>
        <select
          className="select"
          value={pageSize}
          onChange={(event) => void changePageSize(Number(event.target.value))}
        >
          <option value={30}>每页 30</option>
          <option value={60}>每页 60</option>
          <option value={120}>每页 120</option>
          <option value={200}>每页 200</option>
        </select>
      </div>

      <div className="content-grid">
        <section>
          {viewMode === "grid" ? (
            <div className="grid">
              {assets.map((asset) => {
                const thumb = thumbnailSrc(asset);
                return (
                  <div
                    className={`asset-card selectable-card ${
                      selectedIdSet.has(asset.id) ? "selected" : ""
                    }`}
                    key={asset.id}
                  >
                    <label className="select-check">
                      <input
                        type="checkbox"
                        checked={selectedIdSet.has(asset.id)}
                        onChange={() => toggleAssetSelection(asset.id)}
                      />
                    </label>
                    <button className="asset-card-main" onClick={() => selectAsset(asset)}>
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
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="table">
              <div className="table-row header batch-table-row">
                <span>选择</span>
                <span>名称</span>
                <span>类型</span>
                <span>大小</span>
                <span>修改时间</span>
              </div>
              {assets.map((asset) => (
                <div className="table-row batch-table-row" key={asset.id}>
                  <span>
                    <input
                      type="checkbox"
                      checked={selectedIdSet.has(asset.id)}
                      onChange={() => toggleAssetSelection(asset.id)}
                    />
                  </span>
                  <button className="table-link" onClick={() => selectAsset(asset)}>
                    {asset.is_favorite ? "★ " : ""}
                    {asset.name}
                  </button>
                  <span>{asset.asset_type}</span>
                  <span>{formatSize(asset.size_bytes)}</span>
                  <span>{formatDate(asset.file_modified_at)}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <aside className="panel">
          {selected ? (
            <>
              <div className="section-title">
                <h2>{selected.name}</h2>
                <button
                  className="button ghost"
                  onClick={() => {
                    aiController?.abort();
                    setAiSuggestion(null);
                    setSelected(null);
                  }}
                >
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
                {aiLoading ? (
                  <button className="button secondary" onClick={() => aiController?.abort()}>
                    取消分析
                  </button>
                ) : (
                  <button className="button secondary" onClick={analyzeAsset}>
                    智能分析
                  </button>
                )}
                <button className="button" onClick={saveDetails}>
                  保存详情
                </button>
                <button className="button secondary" onClick={moveToTrash}>
                  移入回收站
                </button>
              </div>
              {aiSuggestion ? (
                <div className="field">
                  <span className="label">
                    分析建议 · {aiSuggestion.source === "openai-compatible" ? "远端模型" : "本地规则"}
                  </span>
                  <span className="asset-sub">
                    {aiSuggestion.model ? `${aiSuggestion.model} · ` : ""}
                    {aiSuggestion.elapsed_ms > 0 ? `${aiSuggestion.elapsed_ms} ms` : "无需网络调用"}
                  </span>
                  <p>{aiSuggestion.description}</p>
                  <div className="tag-row">
                    {aiSuggestion.tags.map((tag) => (
                      <span className="tag" key={tag}>
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div className="detail-actions">
                    <button className="button" onClick={() => void applyAiSuggestion()}>
                      应用建议
                    </button>
                    <button className="button secondary" onClick={() => setAiSuggestion(null)}>
                      放弃
                    </button>
                  </div>
                </div>
              ) : null}
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
          ) : null}
        </aside>
      </div>
    </AppShell>
  );
}
