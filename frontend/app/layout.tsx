import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Components Workspace",
  description: "Industrial 3D scene workspace for behavior simulation modeling.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
