// FileName: main.ts
import { createApp } from "vue";
import App from "./App.vue";

import "vuetify/styles";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";
import { createPinia } from "pinia";

import "@mdi/font/css/materialdesignicons.css";
import "@/style.css";

const app = createApp(App);
const pinia = createPinia();
const vuetify = createVuetify({
  components,
  directives,
});

app.use(pinia);
app.use(vuetify);
app.mount("#app");
