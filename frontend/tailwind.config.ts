import type { Config } from "tailwindcss";

// Direction 2 — Warm Industrial
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
        // App surfaces — warm stone palette.
        base: "#fafaf9",       // warm stone white
        panel: "#ffffff",      // pure white for cards
        line: "#e7e5e4",       // hairline border
        elev: "#f5f5f4",       // hover / subtle surface

        // Text scale.
        ink: "#1c1917",        // primary text (warm near-black)
        mute: "#57534e",       // secondary
        fade: "#78716c",       // tertiary, captions

        // Accent — burnt orange / terracotta. Substantial, grounded.
        accent: {
          DEFAULT: "oklch(0.55 0.20 35)",
          fg: "#ffffff",        // white text reads cleanly on the orange
        },

        // Stripe brand purple, unchanged across themes.
        stripe: "#635bff",
      },
      fontFamily: {
        // Direction 2: Space Grotesk for headings (geometric but warm),
        // Inter for body. Variable references are bound in app/layout.tsx.
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
};

export default config;
