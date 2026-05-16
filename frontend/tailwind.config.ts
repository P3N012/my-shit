import type { Config } from "tailwindcss";

// Direction 1 — Monochrome Authority
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // App surfaces — true blacks with a hint of warmth.
        base: "#0a0a0a",
        panel: "#000000",
        line: "#1a1a1a",
        elev: "#111111",

        // Text scale.
        ink: "#ffffff",
        mute: "#888888",
        fade: "#666666",

        // Accent — sharp cyan-green, the "trading terminal highlight."
        accent: {
          DEFAULT: "oklch(0.65 0.24 142)",
          fg: "#0a0a0a",
        },

        // Stripe brand purple, for the connection card logo.
        stripe: "#635bff",
      },
      fontFamily: {
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "6px",
        lg: "8px",
      },
    },
  },
  plugins: [],
};

export default config;
