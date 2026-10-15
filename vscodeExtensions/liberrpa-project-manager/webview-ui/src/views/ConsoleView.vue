<!-- FileName: ConsoleView.vue -->
<template>
  <v-card class="mx-auto" max-width="980">
    <v-card-title class="text-h5 pa-5 pb-2">Console</v-card-title>

    <v-card-subtitle class="px-5 pb-4">
      Connect this Editor to LiberRPA Console.
    </v-card-subtitle>

    <v-divider></v-divider>

    <v-card-text class="pa-5">
      <v-alert
        v-if="consoleAccountStore.accountState.message"
        class="mb-5"
        :type="consoleAccountStore.accountState.signedIn ? 'warning' : 'info'"
        variant="tonal">
        {{ consoleAccountStore.accountState.message }}
      </v-alert>

      <v-text-field
        :model-value="consoleAccountStore.accountState.url || 'Not configured'"
        label="Console URL"
        variant="underlined"
        readonly></v-text-field>

      <v-text-field
        :model-value="strConnection"
        label="Last Connection Check"
        variant="underlined"
        readonly></v-text-field>

      <template v-if="consoleAccountStore.accountState.signedIn">
        <v-alert class="mb-5" type="info" variant="tonal">
          Account details show the last successful response, when available. Use Check
          Connection to refresh.
        </v-alert>

        <v-text-field
          :model-value="strAccount"
          label="Account"
          variant="underlined"
          readonly></v-text-field>

        <v-text-field
          :model-value="
            consoleAccountStore.accountState.account?.organization.name ?? 'Unavailable'
          "
          label="Organization"
          variant="underlined"
          readonly></v-text-field>

        <div class="text-subtitle-1 font-weight-bold mb-2">Account Departments</div>

        <div v-if="consoleAccountStore.accountState.account?.is_org_admin" class="mb-3">
          Organization Administrator — all departments
        </div>

        <v-list
          v-if="consoleAccountStore.accountState.account?.account_departments.length"
          class="mb-4"
          lines="two"
          border
          rounded>
          <v-list-item
            v-for="department in consoleAccountStore.accountState.account
              .account_departments"
            :key="department.id"
            :title="department.path"
            :subtitle="
              department.role === null
                ? 'Organization Administrator'
                : department.role === ConsoleDepartmentRole.Developer
                  ? 'Developer'
                  : 'Operator'
            "></v-list-item>
        </v-list>

        <div v-else class="mb-5 text-medium-emphasis">
          {{
            consoleAccountStore.accountState.account === null
              ? "Unavailable"
              : "No department access."
          }}
        </div>

        <v-text-field
          :model-value="strLastContact"
          label="Last Successful Contact"
          variant="underlined"
          readonly></v-text-field>
      </template>
    </v-card-text>

    <v-divider></v-divider>

    <v-card-actions class="pa-5 flex-wrap ga-2">
      <v-btn
        v-if="consoleAccountStore.accountState.signedIn"
        variant="tonal"
        prepend-icon="mdi-refresh"
        :disabled="boolBusy"
        @click="checkConnection">
        Check Connection
      </v-btn>

      <v-spacer></v-spacer>

      <v-btn
        variant="tonal"
        prepend-icon="mdi-link-edit"
        :disabled="boolBusy"
        @click="openAddress">
        Change Address
      </v-btn>

      <v-btn
        v-if="consoleAccountStore.accountState.signedIn"
        variant="tonal"
        prepend-icon="mdi-logout"
        :disabled="boolBusy"
        @click="signOut">
        Sign Out
      </v-btn>

      <v-btn
        v-else
        color="primary"
        variant="tonal"
        append-icon="mdi-arrow-right"
        :disabled="boolBusy || !consoleAccountStore.accountState.url"
        @click="openSignIn">
        Sign In
      </v-btn>
    </v-card-actions>

    <v-progress-linear v-if="boolBusy" indeterminate></v-progress-linear>
  </v-card>

  <v-dialog v-model="consoleAccountStore.showAddress" max-width="600" persistent>
    <v-card title="Change Console Address">
      <v-card-text>
        <p class="mb-5">Changing the Console URL requires signing in again.</p>

        <v-text-field
          v-model="strUrlDraft"
          label="Console URL"
          placeholder="https://console.example.com"
          :disabled="boolBusy"
          :error-messages="consoleAccountStore.addressError"
          @keydown.enter="changeAddress"></v-text-field>
      </v-card-text>

      <v-card-actions class="pa-4">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="consoleAccountStore.showAddress = false">
          Cancel
        </v-btn>

        <v-spacer></v-spacer>

        <v-btn
          prepend-icon="mdi-content-save-outline"
          color="primary"
          variant="tonal"
          :disabled="boolBusy || !strUrlDraft.trim()"
          :loading="boolBusy"
          @click="changeAddress">
          {{ boolBusy ? "Validating…" : "Validate and Save" }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="consoleAccountStore.showSignIn" max-width="520" persistent>
    <v-card title="Sign In to Console">
      <v-card-text>
        <div class="mb-5 text-break">{{ consoleAccountStore.accountState.url }}</div>

        <v-alert
          v-if="consoleAccountStore.signInError"
          type="error"
          class="mb-4"
          variant="tonal">
          {{ consoleAccountStore.signInError }}
        </v-alert>

        <v-text-field
          v-model="strEmail"
          label="Email"
          type="email"
          autocomplete="username"
          :disabled="boolBusy"></v-text-field>

        <v-text-field
          v-model="strPassword"
          label="Password"
          autocomplete="off"
          :type="boolShowPassword ? 'text' : 'password'"
          :disabled="boolBusy"
          @keydown.enter="signIn">
          <template #append-inner>
            <v-btn
              :icon="boolShowPassword ? 'mdi-eye-off' : 'mdi-eye'"
              :aria-label="boolShowPassword ? 'Hide password' : 'Show password'"
              variant="text"
              size="small"
              :disabled="boolBusy"
              @click="boolShowPassword = !boolShowPassword"></v-btn>
          </template>
        </v-text-field>
      </v-card-text>

      <v-card-actions class="pa-4">
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolBusy"
          @click="cancelSignIn">
          Cancel
        </v-btn>

        <v-spacer></v-spacer>

        <v-btn
          append-icon="mdi-arrow-right"
          color="primary"
          variant="tonal"
          :disabled="boolBusy || !strEmail.trim() || !strPassword"
          :loading="boolBusy"
          @click="signIn">
          Sign In
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import { postMessage } from "../Adapter/Extension/vscodeApi";
import { useProjectManagerStore } from "../Application/projectManagerStore";
import { useConsoleAccountStore } from "../Application/Console/consoleAccountStore";
import { ConsoleConnection, ConsoleDepartmentRole } from "../Domain/Console/consoleTypes";

const projectManagerStore = useProjectManagerStore();
const consoleAccountStore = useConsoleAccountStore();
const strUrlDraft = ref("");
const strEmail = ref("");
const strPassword = ref("");
const boolShowPassword = ref(false);
const boolBusy = computed(() => projectManagerStore.busy);

const strConnection = computed(() => {
  switch (consoleAccountStore.accountState.connection) {
    case ConsoleConnection.SignedOut:
      return "Signed Out";
    case ConsoleConnection.Checking:
      return "Checking…";
    case ConsoleConnection.Connected:
      return "Succeeded";
    case ConsoleConnection.Unavailable:
      return "Failed";
    case ConsoleConnection.Blocked:
      return "Access Unavailable";
  }
});

const strAccount = computed(() => {
  const account = consoleAccountStore.accountState.account;
  return account === null
    ? "Unavailable"
    : `${account.user.username} (${account.user.email})`;
});

const strLastContact = computed(() => {
  const strTimestamp = consoleAccountStore.accountState.lastContactAt;
  if (strTimestamp === null) {
    return "Unavailable";
  }

  const dateObj = new Date(strTimestamp);
  const strDate = [
    dateObj.getFullYear(),
    String(dateObj.getMonth() + 1).padStart(2, "0"),
    String(dateObj.getDate()).padStart(2, "0"),
  ].join("-");
  const strTime = [dateObj.getHours(), dateObj.getMinutes(), dateObj.getSeconds()]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
  return `${strDate} ${strTime}`;
});

function openAddress(): void {
  strUrlDraft.value = consoleAccountStore.accountState.url;
  consoleAccountStore.addressError = "";
  consoleAccountStore.showAddress = true;
}

function changeAddress(): void {
  if (boolBusy.value || !strUrlDraft.value.trim()) {
    return;
  }
  projectManagerStore.busy = true;
  consoleAccountStore.addressError = "";
  postMessage({ command: "changeConsoleAddress", url: strUrlDraft.value });
}

function openSignIn(): void {
  strEmail.value = consoleAccountStore.accountState.rememberedEmail;
  strPassword.value = "";
  boolShowPassword.value = false;
  consoleAccountStore.signInError = "";
  consoleAccountStore.showSignIn = true;
}

function cancelSignIn(): void {
  strPassword.value = "";
  boolShowPassword.value = false;
  consoleAccountStore.showSignIn = false;
}

function signIn(): void {
  if (boolBusy.value || !strEmail.value.trim() || !strPassword.value) {
    return;
  }
  const strSubmittedPassword = strPassword.value;
  strPassword.value = "";
  boolShowPassword.value = false;
  projectManagerStore.busy = true;
  consoleAccountStore.signInError = "";
  postMessage({
    command: "signInConsole",
    email: strEmail.value,
    password: strSubmittedPassword,
  });
}

function signOut(): void {
  projectManagerStore.busy = true;
  postMessage({ command: "signOutConsole" });
}

function checkConnection(): void {
  projectManagerStore.busy = true;
  postMessage({ command: "checkConsoleConnection" });
}

watch(
  () => consoleAccountStore.accountState.url,
  () => {
    strEmail.value = consoleAccountStore.accountState.rememberedEmail;
    strPassword.value = "";
    boolShowPassword.value = false;
  },
);

onUnmounted(() => {
  strPassword.value = "";
  consoleAccountStore.showSignIn = false;
  consoleAccountStore.showAddress = false;
});
</script>

<style scoped></style>
