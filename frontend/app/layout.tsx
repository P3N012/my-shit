import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";

import { Providers } from "@/components/providers";

import "./globals.css";

// Direction 2 — Warm Industrial:
//   Headings → Space Grotesk (geometric, slightly wide, friendly).
//   Body → Inter (max legibility at small sizes for tables/labels).
//
// The CSS variable names stay `--font-mono` / `--font-sans` so Tailwind
// config doesn't need to know which fonts are bound — swapping
// directions is a one-file change here.

const heading = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-mono",  // historical name — heading slot
  display: "swap",
});

const body = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "InsightPlus",
  description: "AI-powered revenue and customer intelligence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${heading.variable} ${body.variable}`}>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
