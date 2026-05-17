import type { Config } from "tailwindcss";

// Ember Glow — near-black surfaces, vibrant orange accent with a
// lighter companion for gradients, single typeface (Manrope).
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
        // App surfaces — warm near-black.
        base: "#0f0f0f",
        panel: "#1a1a1a",
        line: "#2a2a2a",
        elev: "#222222",

        // Text scale.
        ink: "#ffffff",
        mute: "#888888",
        fade: "#666666",

        // Accent — vibrant orange + lighter companion for gradient fills.
        accent: {
          DEFAULT: "#ff6b35",
          muted: "#ff8659",
          fg: "#ffffff",
        },

        // Stripe brand purple, unchanged across themes.
        stripe: "#635bff",
      },
      fontFamily: {
        // Single typeface — Manrope at multiple weights.
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-sans)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "10px",
        lg: "14px",
      },
      backgroundImage: {
        "ember-gradient":
          "linear-gradient(135deg, theme('colors.accent.DEFAULT') 0%, theme('colors.accent.muted') 100%)",
      },
    },
  },
  plugins: [],
};

export default config;
