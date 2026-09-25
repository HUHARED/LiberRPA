// FileName: preferencesStore.ts

import { defineStore } from "pinia";

export type ThemePreference = "light" | "dark" | "system";
const STR_THEME_STORAGE_KEY = "liberrpa-console-theme";

function getSavedTheme(): ThemePreference {
  try {
    const strValue = localStorage.getItem(STR_THEME_STORAGE_KEY);
    if (strValue === "light" || strValue === "dark") return strValue;
  } catch {
    // Browser storage can be disabled without preventing sign-in.
  }
  return "system";
}

export const usePreferencesStore = defineStore("preferences", {
  state: () => {
    return {
      theme: getSavedTheme(),
    };
  },
  actions: {
    setTheme(theme: ThemePreference): void {
      this.theme = theme;
      try {
        localStorage.setItem(STR_THEME_STORAGE_KEY, theme);
      } catch {
        // Keep the selection for this tab when persistence is unavailable.
      }
    },
  },
});
