import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:9090",
        changeOrigin: true,
      },
      "/ai": {
        target: process.env.VITE_AI_ORIGIN || "http://localhost:8080",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ai/, "/api/v1"),
      },
    },
  },
});
