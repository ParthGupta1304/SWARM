import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(import.meta.dirname, "."),
      },
    },
    build: { outDir: "../dashboard/site", emptyOutDir: true },
    server: {
      port: 3000,
      host: "127.0.0.1",
      proxy: {
        "/api": "http://127.0.0.1:8080",
        "/market": "http://127.0.0.1:8080",
        "/bazaar": "http://127.0.0.1:8080",
      },
    },
  };
});
