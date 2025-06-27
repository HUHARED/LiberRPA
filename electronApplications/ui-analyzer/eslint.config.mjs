// FileName: eslint.config.mjs
import tseslint from "@electron-toolkit/eslint-config-ts";
import eslintPluginVue from "eslint-plugin-vue";

export default tseslint.config(
  { ignores: ["**/node_modules", "**/dist", "**/out"] },
  tseslint.configs.recommended,
  eslintPluginVue.configs["flat/recommended"],
  {
    files: ["**/*.vue"],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
      },
    },
  },
  {
    files: ["**/*.{ts,mts,tsx,vue}"],
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "vue/require-default-prop": "off",
      "vue/multi-word-component-names": "off",
      "vue/max-attributes-per-line": "off",
      "vue/html-self-closing": "off",
      "vue/html-closing-bracket-newline": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/no-v-html": "off",
      "vue/valid-v-slot": "off",
      "vue/v-slot-style": "off",
      "vue/html-indent": "off",
    },
  }
);
