import type { Config } from "tailwindcss";

// Hybrid — Direction 1 surfaces + warm amber accent from Direction 2.
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
        // App surfaces — Direction 1 black palette.
        base: "#0a0a0a",
        panel: "#000000",
        line: "#1a1a1a",
        elev: "#111111",

        // Text scale.
        ink: "#ffffff",
        mute: "#888888",
        fade: "#666666",

        // Accent — Direction 2's burnt orange, lifted to oklch L=0.7 so
        // it carries on near-black. Same hue family (~35-40), narrower
        // chroma than the original D1 cyan-green to keep the look
        // grounded rather than electric.
        accent: {
          DEFAULT: "oklch(0.7 0.19 40)",
          fg: "#0a0a0a",   // dark text on the orange button reads cleanly
        },

        // Stripe brand purple, unchanged across themes.
        stripe: "#635bff",
      },
      fontFamily: {
        // Direction 1 fonts — JetBrains Mono headings + IBM Plex Sans body.
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
