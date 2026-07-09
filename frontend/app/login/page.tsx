"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("assetvault");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      let token: { access_token: string };
      try {
        token = await apiFetch("/auth/login", {
          method: "POST",
          body: JSON.stringify({ username, password }),
        });
      } catch {
        await apiFetch("/auth/register", {
          method: "POST",
          body: JSON.stringify({ username, password, display_name: username }),
        });
        token = await apiFetch("/auth/login", {
          method: "POST",
          body: JSON.stringify({ username, password }),
        });
      }
      setToken(token.access_token);
      router.push("/library");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    }
  }

  return (
    <div className="auth-page">
      <form className="panel auth-card" onSubmit={submit}>
        <h1>AssetVault</h1>
        <p className="asset-sub">登录或自动创建本地开发账号。</p>
        <label className="field">
          <span className="label">用户名</span>
          <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label className="field">
          <span className="label">密码</span>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error ? <p className="asset-sub">{error}</p> : null}
        <button className="button" type="submit">
          进入素材库
        </button>
      </form>
    </div>
  );
}
