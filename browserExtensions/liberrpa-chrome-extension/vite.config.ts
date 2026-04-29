import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
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
