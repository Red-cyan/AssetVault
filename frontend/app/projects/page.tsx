"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { API_BASE, apiFetch, Asset, AssetList, getToken, Project, ProjectDetail } from "@/lib/api";

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

function roleLabel(role: string) {
  return ROLE_OPTIONS.find(([value]) => value === role)?.[1] ?? role;
}

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<ProjectDetail | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [assetQuery, setAssetQuery] = useState("");
  const [role, setRole] = useState("other");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadProjects() {
    const result = await apiFetch<Project[]>("/projects");
    setProjects(result);
    if (!selected && result.length > 0) {
      await loadProject(result[0].id);
    }
  }

  async function loadProject(projectId: string) {
    setSelected(await apiFetch<ProjectDetail>(`/projects/${projectId}`));
  }

  async function searchAssets() {
    const params = new URLSearchParams();
    if (assetQuery) params.set("q", assetQuery);
    params.set("page_size", "8");
    const result = await apiFetch<AssetList>(`/assets?${params.toString()}`);
    setAssets(result.items);
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    void Promise.all([loadProjects(), searchAssets()]).catch((err) =>
      setError(err instanceof Error ? err.message : "加载项目失败"),
    );
  }, []);

  async function createProject(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    try {
      const project = await apiFetch<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({ name, description }),
      });
      setName("");
      setDescription("");
      await loadProjects();
      await loadProject(project.id);
      setMessage("项目已创建。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建项目失败");
    }
  }

  async function addAsset(assetId: string) {
    if (!selected) return;
    const detail = await apiFetch<ProjectDetail>(`/projects/${selected.id}/assets`, {
      method: "POST",
      body: JSON.stringify({ asset_id: assetId, role }),
    });
    setSelected(detail);
    await loadProjects();
  }

  async function removeAsset(assetId: string) {
    if (!selected) return;
    const detail = await apiFetch<ProjectDetail>(`/projects/${selected.id}/assets/${assetId}`, {
      method: "DELETE",
    });
    setSelected(detail);
    await loadProjects();
  }

  async function deleteProject() {
    if (!selected) return;
    await apiFetch(`/projects/${selected.id}`, { method: "DELETE" });
    setSelected(null);
    await loadProjects();
  }

  async function exportProject(format: "json" | "csv") {
    if (!selected) return;
    setError(null);
    const token = getToken();
    const response = await fetch(`${API_BASE}/projects/${selected.id}/export?format=${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      setError(await response.text());
      return;
    }
    const blob = await response.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `${selected.name}-manifest.${format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
    setMessage(`项目清单已导出为 ${format.toUpperCase()}。`);
  }

  return (
    <AppShell>
      <div className="section-title">
        <h1>项目</h1>
        <button className="button secondary" onClick={() => void loadProjects()}>
          刷新
        </button>
      </div>

      {message ? <p className="asset-sub">{message}</p> : null}
      {error ? <p className="asset-sub">{error}</p> : null}

      <div className="split-grid">
        <aside className="stack">
          <form className="panel" onSubmit={createProject}>
            <h2>新建项目</h2>
            <label className="field">
              <span className="label">项目名称</span>
              <input className="input" value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="field">
              <span className="label">说明</span>
              <textarea
                className="textarea"
                rows={3}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
            <button className="button" type="submit">
              创建
            </button>
          </form>

          <section className="panel">
            <h2>项目列表</h2>
            <div className="stack">
              {projects.map((project) => (
                <button
                  className={`list-item ${selected?.id === project.id ? "active" : ""}`}
                  key={project.id}
                  onClick={() => loadProject(project.id)}
                >
                  <div className="asset-name">{project.name}</div>
                  <div className="asset-sub">{project.asset_count} 个素材</div>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <main className="stack">
          {selected ? (
            <>
              <section className="panel">
                <div className="section-title">
                  <div>
                    <h2>{selected.name}</h2>
                    <p className="asset-sub">{selected.description || "暂无说明"}</p>
                  </div>
                  <button className="button secondary" onClick={deleteProject}>
                    删除项目
                  </button>
                </div>
                <div className="toolbar">
                  <button className="button secondary" onClick={() => void exportProject("json")}>
                    导出 JSON 清单
                  </button>
                  <button className="button secondary" onClick={() => void exportProject("csv")}>
                    导出 CSV 清单
                  </button>
                </div>
                <div className="stat-grid">
                  <div className="stat-card">
                    <div className="label">引用素材</div>
                    <div className="stat-value">{selected.assets.length}</div>
                  </div>
                  <div className="stat-card">
                    <div className="label">角色类型</div>
                    <div className="stat-value">
                      {new Set(selected.assets.map((item) => item.role)).size}
                    </div>
                  </div>
                </div>
              </section>

              <section className="panel">
                <h2>添加素材</h2>
                <div className="toolbar">
                  <input
                    className="input"
                    placeholder="搜索素材名称、路径、备注"
                    value={assetQuery}
                    onChange={(event) => setAssetQuery(event.target.value)}
                  />
                  <select
                    className="select"
                    value={role}
                    onChange={(event) => setRole(event.target.value)}
                  >
                    {ROLE_OPTIONS.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <button className="button" onClick={() => void searchAssets()}>
                    搜索
                  </button>
                </div>
                <div className="table">
                  {assets.map((asset) => (
                    <div className="table-row" key={asset.id}>
                      <span className="asset-name">{asset.name}</span>
                      <span>{asset.asset_type}</span>
                      <span>{formatSize(asset.size_bytes)}</span>
                      <button className="button secondary" onClick={() => addAsset(asset.id)}>
                        加入
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <h2>项目素材</h2>
                <div className="table">
                  <div className="table-row header">
                    <span>名称</span>
                    <span>角色</span>
                    <span>大小</span>
                    <span>操作</span>
                  </div>
                  {selected.assets.map((item) => (
                    <div className="table-row" key={item.asset.id}>
                      <span className="asset-name">{item.asset.name}</span>
                      <span>{roleLabel(item.role)}</span>
                      <span>{formatSize(item.asset.size_bytes)}</span>
                      <button className="button secondary" onClick={() => removeAsset(item.asset.id)}>
                        移除
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            </>
          ) : (
            <section className="panel">
              <h2>项目详情</h2>
              <p className="asset-sub">创建或选择一个项目，把人物、动作、舞台、音乐等素材组织到作品中。</p>
            </section>
          )}
        </main>
      </div>
    </AppShell>
  );
}
