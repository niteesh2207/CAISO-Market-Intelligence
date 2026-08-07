import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://caiso-market-intelligence-workspace.mallavarapu-r.chatgpt.site"),
  title: "CAISO Market Intelligence Workspace",
  description: "Google-like CAISO and energy-market research with evidence tabs, source provenance, freshness controls, and entitlement-safe premium connectors.",
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
  openGraph: {
    title: "CAISO Market Intelligence Workspace",
    description: "Ask. Verify. Decide. Official-source energy-market research in one workspace.",
    images: [{ url: "/og.png", width: 1536, height: 1024 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "CAISO Market Intelligence Workspace",
    description: "Official-source energy-market research in one workspace.",
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body>
    </html>
  );
}
