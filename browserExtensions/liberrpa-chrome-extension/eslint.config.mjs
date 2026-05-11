// FileName: eslint.config.mjs
// @ts-check

import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import globals from "globals";
import tseslint from "typescript-eslint";
import unusedImports from "eslint-plugin-unused-imports";

export default defineConfig([
  {
    ignores: [
      "node_modules/**",
      "dist/**",
      "build/**",
      "coverage/**",
      "upload_to_chrome_web_store/**",
      "*.zip",
    ],
  },

  {
    files: ["**/*.{js,mjs,cjs}"],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.node,
      },
    },
  },

  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      tseslint.configs.recommendedTypeChecked,
      tseslint.configs.stylisticTypeChecked,
    ],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        projectService: true,
      },
      ecmaVersion: 2022,
      sourceType: "module",
    },
    plugins: {
      "unused-imports": unusedImports,
    },
    rules: {
      "no-undef": "off",

      curly: ["warn", "all"],
      eqeqeq: ["warn", "always"],
      semi: ["warn", "always"],

      // "no-console": ["warn", { allow: ["warn", "error"] }],
      "no-console": "off",
      "no-debugger": "error",
      "no-alert": "warn",

      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-throw-literal": "warn",

      "unused-imports/no-unused-imports": "warn",

      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-explicit-any": "warn",

      "@typescript-eslint/consistent-type-imports": [
        "warn",
        {
          prefer: "type-imports",
          fixStyle: "inline-type-imports",
        },
      ],

      "@typescript-eslint/no-floating-promises": [
        "error",
        {
          ignoreVoid: true,
          ignoreIIFE: false,
        },
      ],
      "@typescript-eslint/no-misused-promises": "error",
      "@typescript-eslint/await-thenable": "error",
      "@typescript-eslint/no-unnecessary-type-assertion": "warn",
      "@typescript-eslint/prefer-optional-chain": "warn",
      "@typescript-eslint/prefer-nullish-coalescing": "warn",
      /* "@typescript-eslint/no-inferrable-types": [
        "warn",
        {
          ignoreParameters: true,
          ignoreProperties: false,
        },
      ], */
      "@typescript-eslint/no-inferrable-types": "off",
    },
  },

  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: [
                "node:*",
                "fs",
                "path",
                "os",
                "child_process",
                "crypto",
                "http",
                "https",
                "net",
                "tls",
                "zlib",
              ],
              message:
                "Chrome extension runtime code does not run in Node.js. Use Node APIs only in Vite config files or build scripts.",
            },
          ],
        },
      ],
    },
  },

  {
    files: ["src/background/**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.serviceworker,
        chrome: "readonly",
      },
    },
    rules: {
      "no-restricted-globals": [
        "error",
        {
          name: "window",
          message:
            "The background script is a Manifest V3 service worker. Do not use window here.",
        },
        {
          name: "document",
          message:
            "The background script is a Manifest V3 service worker. Do not use document here.",
        },
        {
          name: "localStorage",
          message:
            "Avoid localStorage in Manifest V3 service workers. Prefer chrome.storage or IndexedDB.",
        },
      ],
    },
  },

  {
    files: ["src/content/**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        chrome: "readonly",
      },
    },
  },

  {
    files: ["vite.config.ts"],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
    rules: {
      "no-console": "off",
      "no-restricted-imports": "off",
    },
  },

  {
    files: ["**/*.d.ts"],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-empty-object-type": "off",
      "@typescript-eslint/triple-slash-reference": "off",
      "unused-imports/no-unused-imports": "off",
    },
  },
]);
