// FileName: vite.config.ts
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"), // Define the "@" alias
    },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
    rollupOptions: {
      input: "index.html",
      output: {
        // Remove hash from JS and CSS filenames
        entryFileNames: "assets/[name].js", // For entry JS files
        chunkFileNames: "assets/[name].js", // For chunk JS files
        assetFileNames: (assetInfo) => {
          const name = assetInfo.names?.[0] || "default"; // Safely handle `names`
          const ext = path.extname(name);
          if (ext === ".css") {
            return "assets/[name][extname]";
          }
          if (/\.(woff2?|woff|ttf|eot)$/.test(name)) {
            return "assets/[name][extname]";
          }
          // Keep hashed names for other assets (like images)
          return "assets/[name]-[hash][extname]";
        },
      },
    },
  },
});
