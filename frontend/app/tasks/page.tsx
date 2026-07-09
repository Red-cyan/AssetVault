"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { apiFetch, getToken, Task } from "@/lib/api";

const STATUS_LABELS: Record<Task["status"], string> = {
  pending: "等待中",
  running: "运行中",
  success: "成功",
  failed: "失败",
  canceled: "已取消",
};

function formatDate(value: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN");
}

function formatObject(value: Record<string, unknown> | null) {
  if (!value || Object.keys(value).length === 0) return "-";
  return Object.entries(value)
    .map(([key, item]) => `${key}: ${String(item)}`)
    .join("，");
}

export default function TasksPage() {
  const router = useRouter();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function loadTasks() {
    setError(null);
    try {
      setTasks(await apiFetch<Task[]>("/tasks"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载任务失败");
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    void loadTasks();
  }, [router]);

  const runningCount = useMemo(
    () => tasks.filter((task) => task.status === "pending" || task.status === "running").length,
    [tasks],
  );

  return (
    <AppShell>
      <div className="section-title">
        <div>
          <h1>任务</h1>
          <p className="asset-sub">查看扫描、同步等后台任务的最近 50 条记录。</p>
        </div>
        <button className="button secondary" onClick={() => void loadTasks()}>
          刷新
        </button>
      </div>

      {error ? <p className="asset-sub">{error}</p> : null}

      <section className="stat-grid">
        <div className="stat-card">
          <div className="label">任务总数</div>
          <div className="stat-value">{tasks.length}</div>
        </div>
        <div className="stat-card">
          <div className="label">运行中</div>
          <div className="stat-value">{runningCount}</div>
        </div>
        <div className="stat-card">
          <div className="label">最近任务</div>
          <div className="stat-value">{tasks[0] ? STATUS_LABELS[tasks[0].status] : "-"}</div>
        </div>
      </section>

      <section className="panel">
        <h2>任务历史</h2>
        {tasks.length === 0 ? <p className="asset-sub">暂无任务记录。</p> : null}
        <div className="table">
          <div className="table-row task-table-row header">
            <span>类型</span>
            <span>状态</span>
            <span>进度</span>
            <span>结果</span>
            <span>时间</span>
          </div>
          {tasks.map((task) => (
            <div className="table-row task-table-row" key={task.id}>
              <span>
                <strong>{task.type}</strong>
                <span className="asset-sub">{task.message || task.id}</span>
              </span>
              <span className={`status-pill status-${task.status}`}>
                {STATUS_LABELS[task.status] ?? task.status}
              </span>
              <span>
                {task.progress}% · {task.processed}/{task.total}
              </span>
              <span>
                {task.error ? (
                  <span className="asset-sub">{task.error}</span>
                ) : (
                  <span className="asset-sub">{formatObject(task.result)}</span>
                )}
              </span>
              <span className="asset-sub">
                创建：{formatDate(task.created_at)}
                <br />
                完成：{formatDate(task.finished_at)}
              </span>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
