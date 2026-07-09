"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearToken } from "@/lib/api";

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const router = useRouter();

  function logout() {
    clearToken();
    router.push("/login");
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">AssetVault</div>
        <nav className="nav">
          <Link href="/library">素材库</Link>
          <Link href="/projects">项目</Link>
          <Link href="/tags">标签</Link>
          <Link href="/tasks">任务</Link>
          <Link href="/duplicates">重复检测</Link>
          <Link href="/missing">失效素材</Link>
          <Link href="/trash">回收站</Link>
          <Link href="/stats">统计</Link>
          <Link href="/settings">设置</Link>
        </nav>
        <button className="logout-button" onClick={logout}>
          退出登录
        </button>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
