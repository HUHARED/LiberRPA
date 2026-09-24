// FileName: preferences.ts

import { ref } from "vue";
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

export const usePreferencesStore = defineStore("preferences", () => {
  const strTheme = ref<ThemePreference>(getSavedTheme());
  function setTheme(theme: ThemePreference): void {
    strTheme.value = theme;
    try {
      localStorage.setItem(STR_THEME_STORAGE_KEY, theme);
    } catch {
      // Keep the selection for this tab when persistence is unavailable.
    }
  }
  return { theme: strTheme, setTheme };
});
