// FileName: main.ts

import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "@/App.vue";

import { createAppRouter } from "@/app/router";
import { vuetify } from "@/app/vuetify";
import { setSessionInvalidatedHandler } from "@/api/client";

import { useSessionStore } from "@/stores/session";

import "@/styles.css";

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);
const sessionStore = useSessionStore(pinia);
setSessionInvalidatedHandler(() => {
  sessionStore.clearSession(sessionStore.session === null ? null : "expired");
});
app.use(createAppRouter(pinia));
app.use(vuetify);
app.mount("#app");
