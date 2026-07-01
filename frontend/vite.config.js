import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API calls to the Flask backend so the frontend can use relative /api URLs.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5001",
        changeOrigin: true,
      },
    },
  },
});
