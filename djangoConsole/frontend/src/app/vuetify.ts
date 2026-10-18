// FileName: vuetify.ts

import "vuetify/styles";
import "@mdi/font/css/materialdesignicons.css";
import "@vue-js-cron/vuetify/dist/vuetify.css";

import { createVuetify } from "vuetify";
import { VChip, VCol, VIcon, VList, VListItem, VMenu, VRow } from "vuetify/components";

import { INT_LIST_PAGE_SIZE } from "@/api/generated/browserApi";

export const vuetify = createVuetify({
  // NOTE: The compiled cron editor resolves these components at runtime.
  components: { VChip, VCol, VIcon, VList, VListItem, VMenu, VRow },
  defaults: {
    // NOTE: Navigation buttons should not inherit the current route's active style.
    VBtn: { active: false },
    VDataTable: {
      itemsPerPage: INT_LIST_PAGE_SIZE,
      itemsPerPageOptions: [INT_LIST_PAGE_SIZE],
    },
  },
  theme: {
    defaultTheme: "light",
    themes: {
      // NOTE: Reserve highlight for important non-interactive text.
      light: {
        colors: {
          highlight: "#A65332",
          inactive: "#66727A",
          "run-timeout": "#E65100",
          "run-interrupted": "#FF5722",
        },
      },
      dark: {
        colors: {
          highlight: "#E8AE8C",
          inactive: "#A8B0B6",
          "run-timeout": "#FFB74D",
          "run-interrupted": "#FF8A65",
        },
      },
    },
  },
});
