// FileName: vite.config.ts

import { fileURLToPath } from "node:url";

import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import vuetify from "vite-plugin-vuetify";

export default defineConfig(({ mode }) => {
  const dictEnvironment = loadEnv(mode, process.cwd(), "CONSOLE_");
  const strBackendUrl = dictEnvironment.CONSOLE_BACKEND_URL ?? "http://127.0.0.1:8000";
  const proxyOptions = {
    "/api/": {
      target: strBackendUrl,
      // Preserve the browser-facing Host so Django can verify the Origin without a CORS exception.
      changeOrigin: false,
      xfwd: false,
      ws: true,
    },
  };
  return {
    plugins: [vue(), vuetify({ autoImport: true })],
    // Auto-imported Vuetify components must not trigger a dependency rebuild on first navigation.
    optimizeDeps: { exclude: ["vuetify"] },
    resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      proxy: proxyOptions,
    },
    preview: {
      host: "127.0.0.1",
      port: 4173,
      strictPort: true,
      proxy: proxyOptions,
    },
    build: { target: "es2022" },
  };
});
