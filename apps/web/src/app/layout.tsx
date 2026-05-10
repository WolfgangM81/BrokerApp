import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BrokerApp",
  description: "ML-powered stock forecast and decision-support tool.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return children;
}
