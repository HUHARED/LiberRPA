<!-- FileName: Console.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Console</v-label>

    <v-container class="flex-column-grow-1" style="min-width: 100%">
      <v-alert v-if="account.message" type="info" variant="tonal" class="mb-4">
        {{ account.message }}
      </v-alert>

      <v-alert v-if="strPageError" type="error" variant="tonal" class="mb-4">
        {{ strPageError }}
      </v-alert>

      <v-text-field
        label="Console URL"
        variant="underlined"
        :model-value="account.consoleUrl || 'Not configured'"
        readonly />

      <v-text-field
        label="Connection"
        variant="underlined"
        :model-value="strConnectionLabel"
        readonly />

      <template v-if="sessionInfo && !boolSelectingExecutor">
        <v-text-field
          label="Account"
          variant="underlined"
          :model-value="`${sessionInfo.user.username} (${sessionInfo.user.email})`"
          readonly />

        <v-text-field
          label="Organization"
          variant="underlined"
          :model-value="sessionInfo.organization.name"
          readonly />

        <v-textarea
          label="Account Departments"
          variant="underlined"
          :model-value="strAccountDepartments"
          readonly
          auto-grow
          rows="1" />

        <v-text-field
          label="Executor"
          variant="underlined"
          :model-value="sessionInfo.executor?.name"
          readonly />

        <v-text-field
          label="Executor Department"
          variant="underlined"
          :model-value="strExecutorDepartment"
          readonly />

        <v-text-field
          label="Console Dispatch"
          variant="underlined"
          :model-value="strDispatchLabel"
          readonly />

        <v-text-field
          v-if="sessionInfo.last_seen_at"
          label="Last Contact"
          variant="underlined"
          :model-value="strLastContact"
          readonly />
      </template>

      <v-alert v-if="account.hasActiveRun" type="info" variant="tonal" class="mb-4">
        Wait for all actual Runs to finish or stop them before signing out or changing the
        Console address.
      </v-alert>

      <div class="d-flex ga-3">
        <v-btn
          variant="tonal"
          :disabled="boolBusy || boolSelectingExecutor"
          @click="openAddressDialog">
          Change Address
        </v-btn>

        <v-btn
          v-if="!account.hasCredential"
          color="primary"
          variant="tonal"
          :disabled="boolBusy || !account.consoleUrl"
          @click="openSignInDialog">
          Sign In
        </v-btn>

        <v-btn
          v-else-if="!boolSelectingExecutor"
          variant="tonal"
          :disabled="boolBusy || account.hasActiveRun"
          @click="signOut">
          Sign Out
        </v-btn>
      </div>

      <v-card v-if="boolSelectingExecutor" title="Select Executor" class="mt-4">
        <v-card-text>
          <p class="mb-4">Choose an available Executor. Cancel ends this login.</p>

          <v-alert v-if="strSelectionError" type="error" variant="tonal" class="mb-4">
            {{ strSelectionError }}
          </v-alert>

          <v-radio-group
            v-model="strExecutorId"
            :disabled="boolBusy"
            aria-label="Available Executors"
            hide-details>
            <v-table>
              <thead>
                <tr>
                  <th>Select</th>
                  <th>Name</th>
                  <th>Department</th>
                  <th>Console Dispatch</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="executor in executorPage.executors" :key="executor.id">
                  <td>
                    <v-radio :value="executor.id" :aria-label="`Select ${executor.name}`" />
                  </td>
                  <td>{{ executor.name }}</td>
                  <td>{{ executor.department.path }}</td>
                  <td>{{ executor.dispatch_enabled ? "Enabled" : "Paused" }}</td>
                </tr>
                <tr v-if="executorPage.executors.length === 0">
                  <td colspan="4">
                    No available Executors. Create or unassociate an Executor in Console,
                    then refresh.
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-radio-group>

          <v-pagination
            v-if="executorPage.total_pages > 1"
            :model-value="executorPage.page"
            :length="executorPage.total_pages"
            :disabled="boolBusy"
            @update:model-value="loadChoices" />

          <v-alert v-if="account.hasActiveRun" type="info" variant="tonal" class="mt-4">
            Wait for actual Runs to finish before cancelling this login. You can stop Runs
            from Run History, then return here.
          </v-alert>
        </v-card-text>

        <v-card-actions>
          <v-btn
            variant="tonal"
            :disabled="boolBusy"
            @click="loadChoices(executorPage.page)">
            Refresh
          </v-btn>

          <v-spacer />
          <v-btn
            variant="tonal"
            :disabled="boolBusy || account.hasActiveRun"
            @click="signOut">
            Cancel
          </v-btn>

          <v-btn
            variant="tonal"
            color="primary"
            :disabled="boolBusy || !strExecutorId"
            :loading="boolBusy"
            @click="associateExecutor">
            Select Executor
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-container>

    <v-dialog v-model="boolShowAddress" persistent max-width="650">
      <v-card title="Change Address">
        <v-form @submit.prevent="saveAddress">
          <v-card-text>
            <p class="mb-4">Changing the Console URL requires signing in again.</p>

            <v-text-field
              v-model="strAddress"
              label="Console URL"
              autofocus
              :disabled="boolBusy"
              :error-messages="strAddressError" />

            <v-alert v-if="account.hasActiveRun" type="info" variant="tonal">
              Wait for all actual Runs to finish before applying a different address.
            </v-alert>
          </v-card-text>

          <v-card-actions>
            <v-spacer />
            <v-btn variant="tonal" :disabled="boolBusy" @click="boolShowAddress = false">
              Cancel
            </v-btn>
            <v-btn
              variant="tonal"
              type="submit"
              color="primary"
              :disabled="boolBusy || !strAddress.trim() || account.hasActiveRun"
              :loading="boolBusy">
              {{ boolBusy ? "Validating…" : "Validate and Save" }}
            </v-btn>
          </v-card-actions>
        </v-form>
      </v-card>
    </v-dialog>

    <v-dialog v-model="boolShowSignIn" persistent max-width="550">
      <v-card title="Sign In to Console">
        <v-form @submit.prevent="signIn">
          <v-card-text>
            <v-alert v-if="strSignInError" type="error" variant="tonal" class="mb-4">
              {{ strSignInError }}
            </v-alert>

            <v-text-field
              v-model="strEmail"
              label="Email"
              type="email"
              autocomplete="username"
              autofocus
              :disabled="boolBusy" />

            <v-text-field
              v-model="strPassword"
              label="Password"
              :type="boolShowPassword ? 'text' : 'password'"
              autocomplete="current-password"
              :append-inner-icon="boolShowPassword ? 'mdi-eye-off' : 'mdi-eye'"
              :disabled="boolBusy"
              @click:append-inner="boolShowPassword = !boolShowPassword" />
          </v-card-text>

          <v-card-actions>
            <v-spacer />
            <v-btn variant="tonal" :disabled="boolBusy" @click="closeSignInDialog">
              Cancel
            </v-btn>
            <v-btn
              variant="tonal"
              color="primary"
              type="submit"
              :disabled="boolBusy || !strEmail.trim() || !strPassword"
              :loading="boolBusy">
              Sign In
            </v-btn>
          </v-card-actions>
        </v-form>
      </v-card>
    </v-dialog>
  </v-container>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

import {
  ConsoleConnection,
  type ConsoleExecutorPage,
} from "../../../../shared/consoleAccount";
import { getErrorMessage } from "../../../../shared/error";
import type {
  ExecutorInvokeCommand,
  ExecutorInvokeRequest,
  ExecutorInvokeResponse,
  TypeIpcArgs,
} from "../../../../shared/ipc";
import { useConsoleStore } from "../../Store/consoleStore";
import { useSettingStore } from "../../Store/settingStore";
import { formatTimestamp } from "../../Common/time";

const consoleStore = useConsoleStore();
const settingStore = useSettingStore();
const account = computed(() => consoleStore.account);
const sessionInfo = computed(() => account.value.sessionInfo);
const boolBusy = computed(() => consoleStore.boolWorking || account.value.busy);
const boolSelectingExecutor = computed(
  () => sessionInfo.value?.session.selection_required === true,
);
const boolShowAddress = ref(false);
const boolShowSignIn = ref(false);
const boolShowPassword = ref(false);
const strAddress = ref("");
const strEmail = ref("");
const strPassword = ref("");
const strAddressError = ref("");
const strSignInError = ref("");
const strSelectionError = ref("");
const strPageError = ref("");
const strExecutorId = ref<string | null>(null);
const executorPage = ref<ConsoleExecutorPage>({ executors: [], page: 1, total_pages: 1 });

const DICT_CONNECTION_LABEL: Record<ConsoleConnection, string> = {
  [ConsoleConnection.SignedOut]: "Signed Out",
  [ConsoleConnection.SelectingExecutor]: "Select Executor",
  [ConsoleConnection.Connected]: "Connected",
  [ConsoleConnection.Reconnecting]: "Reconnecting",
  [ConsoleConnection.AccessUnavailable]: "Access Unavailable",
};
const strConnectionLabel = computed(() => DICT_CONNECTION_LABEL[account.value.connection]);
const strAccountDepartments = computed(() => {
  if (sessionInfo.value?.is_org_admin) {
    return "OrgAdmin — All departments";
  }
  return (
    sessionInfo.value?.account_departments
      .map((department) => `${department.path} (${department.role})`)
      .join("\n") || "No department access"
  );
});
const strExecutorDepartment = computed(
  () =>
    sessionInfo.value?.account_departments.find(
      (department) => department.id === sessionInfo.value?.executor?.department_id,
    )?.path || "—",
);
const strDispatchLabel = computed(() => {
  const strValue = sessionInfo.value?.executor?.dispatch_enabled ? "Enabled" : "Paused";
  return account.value.connection === ConsoleConnection.Connected
    ? strValue
    : `${strValue} (last received)`;
});
const strLastContact = computed(() => {
  const strTimestamp = sessionInfo.value?.last_seen_at ?? null;
  return strTimestamp === null
    ? "Unavailable"
    : formatTimestamp(Date.parse(strTimestamp), settingStore.timezone);
});

async function invokeConsole<C extends ExecutorInvokeCommand>(
  command: C,
  ...args: TypeIpcArgs<ExecutorInvokeRequest<C>>
): Promise<ExecutorInvokeResponse<C>> {
  const result = await window.executor.invoke(command, ...args);
  if (!result.success) {
    throw new Error(result.error);
  }
  return result.data;
}

function closeSignInDialog(): void {
  boolShowSignIn.value = false;
  strPassword.value = "";
  boolShowPassword.value = false;
}

function openSignInDialog(): void {
  strEmail.value = account.value.rememberedEmail;
  strSignInError.value = "";
  boolShowSignIn.value = true;
}

function openAddressDialog(): void {
  strAddress.value = account.value.consoleUrl;
  strAddressError.value = "";
  boolShowAddress.value = true;
}

async function loadChoices(page: number): Promise<void> {
  if (consoleStore.boolWorking || !boolSelectingExecutor.value) {
    return;
  }
  consoleStore.boolWorking = true;
  strSelectionError.value = "";
  try {
    executorPage.value = await invokeConsole("getConsoleExecutorChoices", page);
    strExecutorId.value = null;
  } catch (e: unknown) {
    strSelectionError.value = getErrorMessage(e);
  } finally {
    consoleStore.boolWorking = false;
  }
}

async function saveAddress(): Promise<void> {
  consoleStore.boolWorking = true;
  strAddressError.value = "";
  try {
    await invokeConsole("saveConsoleAddress", strAddress.value);
    boolShowAddress.value = false;
  } catch (e: unknown) {
    strAddressError.value = getErrorMessage(e);
  } finally {
    consoleStore.boolWorking = false;
  }
}

async function signIn(): Promise<void> {
  consoleStore.boolWorking = true;
  strSignInError.value = "";
  try {
    await invokeConsole("signInConsole", {
      email: strEmail.value,
      password: strPassword.value,
    });
    closeSignInDialog();
  } catch (e: unknown) {
    strSignInError.value = getErrorMessage(e);
  } finally {
    strPassword.value = "";
    boolShowPassword.value = false;
    consoleStore.boolWorking = false;
  }
  await loadChoices(1);
}

async function associateExecutor(): Promise<void> {
  if (!strExecutorId.value) {
    return;
  }
  consoleStore.boolWorking = true;
  strSelectionError.value = "";
  try {
    await invokeConsole("associateConsoleExecutor", strExecutorId.value);
  } catch (e: unknown) {
    strSelectionError.value = getErrorMessage(e);
  } finally {
    consoleStore.boolWorking = false;
  }
}

async function signOut(): Promise<void> {
  consoleStore.boolWorking = true;
  strPageError.value = "";
  strSelectionError.value = "";
  try {
    await invokeConsole("signOutConsole");
  } catch (e: unknown) {
    if (boolSelectingExecutor.value) {
      strSelectionError.value = getErrorMessage(e);
    } else {
      strPageError.value = getErrorMessage(e);
    }
  } finally {
    consoleStore.boolWorking = false;
  }
}

watch(
  boolSelectingExecutor,
  (boolSelecting) => {
    if (boolSelecting) {
      void loadChoices(1);
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  strPassword.value = "";
});
</script>
<style scoped></style>
