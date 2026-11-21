import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "AI API 中转站" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="en"><body>{children}</body></html>);
}
