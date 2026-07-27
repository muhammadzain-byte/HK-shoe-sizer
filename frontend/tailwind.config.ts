import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18181b",
        porcelain: "#f7f8f5",
        clay: "#9f5f4b",
        sage: "#6d8b74",
        lilac: "#9c7aa5",
      },
      boxShadow: {
        panel: "0 18px 50px rgba(24, 24, 27, 0.10)",
      },
    },
  },
  plugins: [],
};

export default config;

