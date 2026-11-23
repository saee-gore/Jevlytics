import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        muted: "#64748b",
        line: "#e2e8f0",
        surface: "#ffffff",
        canvas: "#f6f7f9",
        accent: { DEFAULT: "#2563eb", soft: "#eff6ff" },
        violet: { DEFAULT: "#7c3aed", soft: "#f5f3ff" },
        teal: { DEFAULT: "#0d9488", soft: "#f0fdfa" },
        rose: { DEFAULT: "#e11d48", soft: "#fff1f2" },
        amber: { DEFAULT: "#d97706", soft: "#fffbeb" },
        sky: { DEFAULT: "#0284c7", soft: "#f0f9ff" },
        warn: "#b45309",
        danger: "#b91c1c",
        ok: "#15803d",
      },
      backgroundImage: {
        brand: "linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)",
        "brand-soft": "linear-gradient(135deg, #eff6ff 0%, #f5f3ff 100%)",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Helvetica", "Arial", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06)",
        lift: "0 12px 28px -12px rgba(37, 99, 235, 0.18), 0 2px 6px rgba(15, 23, 42, 0.05)",
        glow: "0 12px 30px -8px rgba(124, 58, 237, 0.55)",
        panel: "0 30px 70px -20px rgba(15, 23, 42, 0.4)",
      },
    },
  },
  plugins: [],
};

export default config;
