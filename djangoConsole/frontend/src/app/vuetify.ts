// FileName: vuetify.ts

import "vuetify/styles";
import "@mdi/font/css/materialdesignicons.css";
import "@vue-js-cron/vuetify/dist/vuetify.css";

import { createVuetify } from "vuetify";
import { VChip, VCol, VIcon, VList, VListItem, VMenu, VRow } from "vuetify/components";

export const vuetify = createVuetify({
  // NOTE: The compiled cron editor resolves these components at runtime.
  components: { VChip, VCol, VIcon, VList, VListItem, VMenu, VRow },
  defaults: {
    // NOTE: Navigation buttons should not inherit the current route's active style.
    VBtn: { active: false },
  },
  theme: {
    defaultTheme: "light",
    themes: {
      // NOTE: Reserve highlight for important non-interactive text.
      light: { colors: { highlight: "#A65332", inactive: "#66727A" } },
      dark: { colors: { highlight: "#E8AE8C", inactive: "#A8B0B6" } },
    },
  },
});
