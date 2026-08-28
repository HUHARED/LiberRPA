// FileName: main.ts

import "./assets/main.css";

import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";

// Vuetify
import "vuetify/styles";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";

import "@mdi/font/css/materialdesignicons.css";

import CronVuetifyPlugin from "@vue-js-cron/vuetify";

import { registerMainMessageListener } from "./IPC/mainMessage";

const THEME_LIGHT = {
  dark: false,
  colors: {
    navigation: "#205781",
    "on-navigation": "#FFFFFF",
    "tab-header-border": "#4F959D",
    "column-header-border": "#98D2C0",
    inactive: "#66727A",
    "run-timeout": "#E65100",
    "run-interrupted": "#FF5722",
  },
};

const THEME_DARK = {
  dark: true,
  colors: {
    navigation: "#163B57",
    "on-navigation": "#FFFFFF",
    "tab-header-border": "#73B8BE",
    "column-header-border": "#5D8B80",
    inactive: "#A8B0B6",
    "run-timeout": "#FFB74D",
    "run-interrupted": "#FF8A65",
  },
};

const app = createApp(App);
const pinia = createPinia();
const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: "light",
    themes: {
      light: THEME_LIGHT,
      dark: THEME_DARK,
    },
  },
});

app.use(pinia);
registerMainMessageListener();
app.use(vuetify);
app.use(CronVuetifyPlugin);
app.mount("#app");
