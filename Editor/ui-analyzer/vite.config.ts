// FileName: vite.config.ts
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// https://vitejs.dev/config/
export default defineConfig({
  // Set the path for electron-builder can find the right renderer file.
  base: "./",
  plugins: [vue()],
});
