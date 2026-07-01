import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 求职助手",
  description: "简历与 JD 匹配分析"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
