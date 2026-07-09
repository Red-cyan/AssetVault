"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { apiFetch, getToken, Tag } from "@/lib/api";

type EditableTag = Tag & {
  draftName: string;
  draftColor: string;
};

const DEFAULT_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2"];

function toEditable(tag: Tag): EditableTag {
  return {
    ...tag,
    draftName: tag.name,
    draftColor: tag.color ?? "",
  };
}

export default function TagsPage() {
  const router = useRouter();
  const [tags, setTags] = useState<EditableTag[]>([]);
  const [name, setName] = useState("");
  const [color, setColor] = useState(DEFAULT_COLORS[0]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadTags() {
    const result = await apiFetch<Tag[]>("/tags");
    setTags(result.map(toEditable));
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    void loadTags().catch((err) => setError(err instanceof Error ? err.message : "加载标签失败"));
  }, [router]);

  async function createTag(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    try {
      await apiFetch<Tag>("/tags", {
        method: "POST",
        body: JSON.stringify({ name, color }),
      });
      setName("");
      setColor(DEFAULT_COLORS[0]);
      await loadTags();
      setMessage("标签已创建。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建标签失败");
    }
  }

  async function updateTag(tag: EditableTag) {
    setError(null);
    setMessage(null);
    try {
      await apiFetch<Tag>(`/tags/${tag.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: tag.draftName,
          color: tag.draftColor || null,
        }),
      });
      await loadTags();
      setMessage("标签已更新。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新标签失败");
    }
  }

  async function deleteTag(tagId: string) {
    setError(null);
    setMessage(null);
    try {
      await apiFetch<void>(`/tags/${tagId}`, { method: "DELETE" });
      await loadTags();
      setMessage("标签已删除，素材文件和素材索引不会被删除。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除标签失败");
    }
  }

  function updateDraft(tagId: string, patch: Partial<Pick<EditableTag, "draftName" | "draftColor">>) {
    setTags((items) => items.map((item) => (item.id === tagId ? { ...item, ...patch } : item)));
  }

  return (
    <AppShell>
      <div className="section-title">
        <h1>标签</h1>
        <button className="button secondary" onClick={() => void loadTags()}>
          刷新
        </button>
      </div>

      {message ? <p className="asset-sub">{message}</p> : null}
      {error ? <p className="asset-sub">{error}</p> : null}

      <div className="split-grid">
        <form className="panel" onSubmit={createTag}>
          <h2>新建标签</h2>
          <label className="field">
            <span className="label">名称</span>
            <input
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="label">颜色</span>
            <input
              className="input"
              type="color"
              value={color}
              onChange={(event) => setColor(event.target.value)}
            />
          </label>
          <div className="tag-row">
            {DEFAULT_COLORS.map((item) => (
              <button
                className="color-swatch"
                key={item}
                style={{ backgroundColor: item }}
                type="button"
                title={item}
                onClick={() => setColor(item)}
              />
            ))}
          </div>
          <button className="button" type="submit">
            创建标签
          </button>
        </form>

        <section className="panel">
          <h2>标签列表</h2>
          {tags.length === 0 ? <p className="asset-sub">暂无标签。</p> : null}
          <div className="table">
            <div className="table-row tag-table-row header">
              <span>预览</span>
              <span>名称</span>
              <span>来源</span>
              <span>颜色</span>
              <span>操作</span>
            </div>
            {tags.map((tag) => (
              <div className="table-row tag-table-row" key={tag.id}>
                <span>
                  <span
                    className="tag"
                    style={tag.draftColor ? { backgroundColor: tag.draftColor, color: "white" } : {}}
                  >
                    {tag.draftName || "未命名"}
                  </span>
                </span>
                <input
                  className="input"
                  value={tag.draftName}
                  onChange={(event) => updateDraft(tag.id, { draftName: event.target.value })}
                />
                <span>{tag.source === "ai" ? "AI" : "手动"}</span>
                <input
                  className="input"
                  type="color"
                  value={tag.draftColor || "#2563eb"}
                  onChange={(event) => updateDraft(tag.id, { draftColor: event.target.value })}
                />
                <span className="detail-actions">
                  <button className="button secondary" onClick={() => void updateTag(tag)}>
                    保存
                  </button>
                  <button className="button secondary" onClick={() => void deleteTag(tag.id)}>
                    删除
                  </button>
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
