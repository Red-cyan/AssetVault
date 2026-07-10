"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { FolderPlus, RefreshCw, Trash2 } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { apiFetch, Folder, Task } from "@/lib/api";

function formatDate(value: string | null) {
  if (!value) return "尚未扫描";
  return new Date(value).toLocaleString("zh-CN");
}

export default function SourcesPage() {
  const [folders, setFolders] = useState<Folder[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [path, setPath] = useState("");
  const [busyFolderId, setBusyFolderId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeFolderIds = useMemo(
    () =>
      new Set(
        tasks
          .filter((task) => task.status === "pending" || task.status === "running")
          .map((task) => String(task.payload?.folder_id ?? "")),
      ),
    [tasks],
  );

  async function loadData() {
    const [folderList, taskList] = await Promise.all([
      apiFetch<Folder[]>("/folders"),
      apiFetch<Task[]>("/tasks"),
    ]);
    setFolders(folderList);
    setTasks(taskList);
  }

  useEffect(() => {
    void loadData().catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  useEffect(() => {
    if (activeFolderIds.size === 0) return;
    const timer = window.setInterval(() => void loadData(), 1800);
    return () => window.clearInterval(timer);
  }, [activeFolderIds.size]);

  async function addFolder(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setError(null);
    try {
      const folder = await apiFetch<Folder>("/folders", {
        method: "POST",
        body: JSON.stringify({ path }),
      });
      setPath("");
      await apiFetch<Task>(`/folders/${folder.id}/scan`, { method: "POST" });
      await loadData();
      setMessage("数据源已添加，扫描任务已进入任务中心。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加数据源失败");
    }
  }

  async function scanFolder(folderId: string) {
    setBusyFolderId(folderId);
    setMessage(null);
    setError(null);
    try {
      await apiFetch<Task>(`/folders/${folderId}/scan`, { method: "POST" });
      await loadData();
      setMessage("扫描任务已创建。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建扫描任务失败");
    } finally {
      setBusyFolderId(null);
    }
  }

  async function removeFolder(folder: Folder) {
    if (!window.confirm(`移除数据源“${folder.name}”？已有素材索引和原始文件不会被删除。`)) {
      return;
    }
    setError(null);
    try {
      await apiFetch<void>(`/folders/${folder.id}`, { method: "DELETE" });
      await loadData();
      setMessage("数据源已移除，已有素材索引保持不变。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "移除数据源失败");
    }
  }

  return (
    <AppShell>
      <div className="section-title">
        <div>
          <h1>数据源</h1>
          <p className="asset-sub">管理后端可访问的本地目录，并启动增量扫描。</p>
        </div>
        <button className="button secondary" onClick={() => void loadData()} title="刷新">
          <RefreshCw size={16} />
          刷新
        </button>
      </div>

      <form className="toolbar" onSubmit={addFolder}>
        <input
          className="input"
          placeholder="输入后端可访问的目录，例如 E:\\Assets"
          value={path}
          onChange={(event) => setPath(event.target.value)}
          required
        />
        <button className="button" type="submit">
          <FolderPlus size={16} />
          添加并扫描
        </button>
      </form>

      {message ? <p className="asset-sub">{message}</p> : null}
      {error ? <p className="asset-sub">{error}</p> : null}

      <section className="panel">
        <h2>已配置目录</h2>
        {folders.length === 0 ? (
          <p className="asset-sub">暂无数据源。添加第一个目录后，素材会在扫描完成后出现在素材库。</p>
        ) : (
          <div className="folder-list">
            {folders.map((folder) => {
              const scanning = activeFolderIds.has(folder.id);
              return (
                <div className="folder-item" key={folder.id}>
                  <div>
                    <div className="asset-name">{folder.name}</div>
                    <div className="asset-sub">{folder.path}</div>
                    <div className="asset-sub">最近扫描：{formatDate(folder.last_scanned_at)}</div>
                  </div>
                  <div className="detail-actions">
                    <button
                      className="button secondary"
                      disabled={scanning || busyFolderId === folder.id}
                      onClick={() => void scanFolder(folder.id)}
                    >
                      <RefreshCw size={16} />
                      {scanning ? "扫描中" : "增量扫描"}
                    </button>
                    <button
                      className="button secondary"
                      disabled={scanning}
                      onClick={() => void removeFolder(folder)}
                      title="移除数据源"
                    >
                      <Trash2 size={16} />
                      移除
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </AppShell>
  );
}
