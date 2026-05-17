import type { Metadata } from "next";
import { Manrope } from "next/font/google";

import { Providers } from "@/components/providers";

import "./globals.css";

// Ember Glow uses Manrope at multiple weights for both display and body.
const sans = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "InsightPlus",
  description: "AI-powered revenue and customer intelligence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={sans.variable}>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
