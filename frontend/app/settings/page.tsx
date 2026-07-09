import { AppShell } from "@/components/AppShell";

export default function SettingsPage() {
  return (
    <AppShell>
      <div className="panel">
        <h1>设置</h1>
        <div className="field">
          <span className="label">素材目录</span>
          <span>当前版本在素材库页面添加和扫描。</span>
        </div>
        <div className="field">
          <span className="label">AI Key</span>
          <span>第二阶段接入 OpenAI Compatible API 后配置。</span>
        </div>
        <div className="field">
          <span className="label">缓存目录</span>
          <span>默认使用 backend 启动目录下的 cache/thumbnails。</span>
        </div>
      </div>
    </AppShell>
  );
}
