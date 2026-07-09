import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AssetVault",
  description: "AI Digital Asset Manager for UE5, Blender & MMD",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
