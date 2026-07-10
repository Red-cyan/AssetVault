"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import {
  apiFetch,
  clearToken,
  getRuntimeInfo,
  getToken,
  RuntimeInfo,
  UserProfile,
} from "@/lib/api";

const RuntimeContext = createContext<RuntimeInfo | null>(null);

export function useRuntime() {
  const runtime = useContext(RuntimeContext);
  if (!runtime) throw new Error("useRuntime must be used inside AppShell");
  return runtime;
}

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const router = useRouter();
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function establishSession() {
      try {
        const info = await getRuntimeInfo();
        if (info.auth_mode === "local") {
          clearToken();
        } else {
          if (!getToken()) {
            router.replace("/login");
            return;
          }
          await apiFetch<UserProfile>("/auth/me");
        }
        if (active) setRuntime(info);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Unable to start session");
      }
    }

    function handleUnauthorized() {
      router.replace("/login");
    }

    window.addEventListener("assetvault:unauthorized", handleUnauthorized);
    void establishSession();
    return () => {
      active = false;
      window.removeEventListener("assetvault:unauthorized", handleUnauthorized);
    };
  }, [router]);

  function logout() {
    clearToken();
    router.replace("/login");
  }

  if (error) {
    return <div className="auth-page"><p className="asset-sub">{error}</p></div>;
  }
  if (!runtime) {
    return <div className="auth-page"><p className="asset-sub">正在连接工作区...</p></div>;
  }

  return (
    <RuntimeContext.Provider value={runtime}>
      <div className="shell">
        <aside className="sidebar">
          <div className="brand">AssetVault</div>
          {runtime.auth_mode === "local" ? <div className="asset-sub">本地工作区</div> : null}
          <nav className="nav">
            <Link href="/library">素材库</Link>
            <Link href="/sources">数据源</Link>
            <Link href="/projects">项目</Link>
            <Link href="/tags">标签</Link>
            <Link href="/tasks">任务</Link>
            <Link href="/duplicates">重复检测</Link>
            <Link href="/missing">失效素材</Link>
            <Link href="/trash">回收站</Link>
            <Link href="/stats">统计</Link>
            <Link href="/settings">设置</Link>
          </nav>
          {runtime.auth_mode === "password" ? (
            <button className="logout-button" onClick={logout}>退出登录</button>
          ) : null}
        </aside>
        <main className="main">{children}</main>
      </div>
    </RuntimeContext.Provider>
  );
}
