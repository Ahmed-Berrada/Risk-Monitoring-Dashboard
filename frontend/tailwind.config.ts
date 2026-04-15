import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#07090f",
          2: "#0d1117",
          3: "#131a26",
        },
        border: {
          DEFAULT: "#1e2d45",
          2: "#243452",
        },
        accent: {
          DEFAULT: "#c8a84b",
          2: "#e8c96a",
          dim: "rgba(200, 168, 75, 0.094)",
          glow: "rgba(200, 168, 75, 0.208)",
        },
        navy: {
          DEFAULT: "#1a3a6b",
          light: "#2a5298",
        },
        text: {
          DEFAULT: "#e9ecf2",
          muted: "#5a6a82",
          dim: "#8a9ab2",
        },
      },
      fontFamily: {
        display: ["Playfair Display", "serif"],
        mono: ["JetBrains Mono", "monospace"],
        body: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
