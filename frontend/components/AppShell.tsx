import Link from "next/link";

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">AssetVault</div>
        <nav className="nav">
          <Link href="/library">素材库</Link>
          <Link href="/projects">项目</Link>
          <Link href="/stats">统计</Link>
          <Link href="/settings">设置</Link>
        </nav>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
