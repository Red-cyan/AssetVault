"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { AiConnectionTestResult, apiFetch, AppSettings, getToken } from "@/lib/api";

export default function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [aiApiKey, setAiApiKey] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    apiFetch<AppSettings>("/settings")
      .then(setSettings)
      .catch((err) => setError(err instanceof Error ? err.message : "加载设置失败"));
  }, [router]);

  function updateField<K extends keyof AppSettings>(key: K, value: AppSettings[K]) {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
  }

  async function saveSettings(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    setError(null);
    setMessage(null);
    try {
      const payload: Record<string, unknown> = {
        cache_dir: settings.cache_dir,
        theme: settings.theme,
        ai_base_url: settings.ai_base_url,
        ai_chat_model: settings.ai_chat_model,
        ai_embedding_model: settings.ai_embedding_model,
        thumbnail_quality: settings.thumbnail_quality,
      };
      if (aiApiKey.trim()) {
        payload.ai_api_key = aiApiKey.trim();
      }
      const updated = await apiFetch<AppSettings>("/settings", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setSettings(updated);
      setAiApiKey("");
      setMessage("设置已保存。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存设置失败");
    }
  }

  async function testAi() {
    setError(null);
    setMessage(null);
    try {
      const result = await apiFetch<AiConnectionTestResult>("/settings/test-ai", {
        method: "POST",
      });
      setMessage(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "测试失败");
    }
  }

  return (
    <AppShell>
      <div className="section-title">
        <h1>设置</h1>
      </div>

      {error ? <p className="asset-sub">{error}</p> : null}
      {message ? <p className="asset-sub">{message}</p> : null}
      {!settings ? <p className="asset-sub">正在加载设置。</p> : null}

      {settings ? (
        <form className="stack" onSubmit={saveSettings}>
          <section className="panel">
            <h2>基础设置</h2>
            <label className="field">
              <span className="label">缓存目录</span>
              <input
                className="input"
                value={settings.cache_dir}
                onChange={(event) => updateField("cache_dir", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">主题</span>
              <select
                className="select"
                value={settings.theme}
                onChange={(event) => updateField("theme", event.target.value)}
              >
                <option value="system">跟随系统</option>
                <option value="light">浅色</option>
                <option value="dark">深色</option>
              </select>
            </label>
            <label className="field">
              <span className="label">缩略图质量</span>
              <input
                className="input"
                type="number"
                min={40}
                max={95}
                value={settings.thumbnail_quality}
                onChange={(event) => updateField("thumbnail_quality", Number(event.target.value))}
              />
            </label>
          </section>

          <section className="panel">
            <h2>AI 设置</h2>
            <label className="field">
              <span className="label">OpenAI Compatible Base URL</span>
              <input
                className="input"
                value={settings.ai_base_url}
                onChange={(event) => updateField("ai_base_url", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">AI Key</span>
              <input
                className="input"
                type="password"
                placeholder={settings.ai_api_key_configured ? "已配置，留空则不修改" : "尚未配置"}
                value={aiApiKey}
                onChange={(event) => setAiApiKey(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">对话模型</span>
              <input
                className="input"
                value={settings.ai_chat_model}
                onChange={(event) => updateField("ai_chat_model", event.target.value)}
              />
            </label>
            <label className="field">
              <span className="label">Embedding 模型</span>
              <input
                className="input"
                value={settings.ai_embedding_model}
                onChange={(event) => updateField("ai_embedding_model", event.target.value)}
              />
            </label>
            <div className="detail-actions">
              <button className="button" type="submit">
                保存设置
              </button>
              <button className="button secondary" type="button" onClick={() => void testAi()}>
                测试 AI 配置
              </button>
            </div>
          </section>
        </form>
      ) : null}
    </AppShell>
  );
}
