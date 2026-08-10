// FileName: eslint.config.mjs
// @ts-check

import globals from "globals";
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import eslintPluginVue from "eslint-plugin-vue";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default tseslint.config(
  {
    ignores: ["**/node_modules/**", "**/dist/**"],
  },

  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  ...eslintPluginVue.configs["flat/recommended"],

  {
    files: ["**/*.vue"],

    languageOptions: {
      globals: {
        ...globals.browser,
      },
      parserOptions: {
        parser: tseslint.parser,
        projectService: true,
        tsconfigRootDir: __dirname,
        extraFileExtensions: [".vue"],
      },
    },
  },

  {
    files: ["**/*.{ts,tsx,vue}"],

    languageOptions: {
      globals: {
        ...globals.browser,
      },
      parserOptions: {
        projectService: true,
        tsconfigRootDir: __dirname,
        extraFileExtensions: [".vue"],
      },
    },

    rules: {
      "@typescript-eslint/explicit-function-return-type": [
        "error",
        {
          allowExpressions: true,
          allowTypedFunctionExpressions: true,
          allowHigherOrderFunctions: true,
          allowDirectConstAssertionInArrowFunctions: true,
          allowIIFEs: true,
        },
      ],

      "@typescript-eslint/no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],

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
          checkThenables: true,
        },
      ],

      "@typescript-eslint/no-misused-promises": "error",
      "@typescript-eslint/await-thenable": "error",

      "@typescript-eslint/no-unnecessary-type-assertion": "warn",

      "vue/require-default-prop": "off",
      "vue/multi-word-component-names": "off",

      "vue/max-attributes-per-line": "off",
      "vue/html-self-closing": "off",
      "vue/html-closing-bracket-newline": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/multiline-html-element-content-newline": "off",
      "vue/html-indent": "off",

      "vue/no-v-html": "warn",
      "vue/valid-v-slot": "off",
      "vue/v-slot-style": "off",

      "vue/html-quotes": [
        "warn",
        "double",
        {
          avoidEscape: true,
        },
      ],
    },
  },
  {
    files: [
      "src/Application/projectManagerStore.ts",
      "src/Application/CreateProject/createProjectStore.ts",
      "src/Application/ComponentManagement/componentManagementStore.ts",
    ],
    rules: {
      "@typescript-eslint/no-unnecessary-type-assertion": "off",
    },
  },
);
