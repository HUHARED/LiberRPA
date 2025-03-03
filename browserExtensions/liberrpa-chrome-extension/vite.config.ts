import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      input: {
        background: "src/background/background.ts",
        content: "src/content/content.ts",
      },
      output: {
        dir: "dist",
        format: "esm", 
        entryFileNames: "[name].js",
        chunkFileNames: "[name].js",
        assetFileNames: "[name].[ext]",
        // inlineDynamicImports: false,
      },
    },
  },
});
