<!-- FileName: RunEmailEditor.vue -->
<template>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-3">
    {{ strError }}
  </v-alert>

  <v-select
    v-model="config.recipient_ids"
    variant="underlined"
    :items="arrRecipient"
    item-title="email"
    item-value="id"
    label="To (verified addresses, up to 5)"
    :error-messages="getFieldErrors(fieldErrors, 'settings.run_email.recipient_ids')"
    multiple
    chips
    :closable-chips="!readonly"
    :disabled="disabled"
    :readonly="readonly"
    :rules="[(value) => value.length <= 5 || 'Select at most 5 addresses.']" />

  <v-expansion-panels v-model="arrOpenPanel" multiple variant="accordion">
    <v-expansion-panel v-for="event in ARR_EVENT" :key="event.key" :value="event.key">
      <v-expansion-panel-title>
        {{ event.title }} · {{ config[event.key].enabled ? "Enabled" : "Disabled" }}
      </v-expansion-panel-title>

      <v-expansion-panel-text>
        <v-switch
          v-model="config[event.key].enabled"
          :error-messages="
            getFieldErrors(fieldErrors, `settings.run_email.${event.key}.enabled`)
          "
          :label="event.title"
          :disabled="disabled"
          :readonly="readonly" />

        <v-text-field
          v-model="config[event.key].subject"
          variant="underlined"
          :error-messages="
            getFieldErrors(fieldErrors, `settings.run_email.${event.key}.subject`)
          "
          label="Subject"
          :disabled="disabled"
          :readonly="readonly"
          @focus="setField(event.key, 'subject')" />

        <v-textarea
          v-model="config[event.key].body"
          variant="underlined"
          :error-messages="
            getFieldErrors(fieldErrors, `settings.run_email.${event.key}.body`)
          "
          label="Body (plain text)"
          rows="5"
          :disabled="disabled"
          :readonly="readonly"
          @focus="setField(event.key, 'body')" />

        <v-menu v-if="!readonly">
          <template #activator="{ props: menuProps }">
            <v-btn v-bind="menuProps" variant="tonal" :disabled="disabled">
              Insert Field
            </v-btn>
          </template>

          <v-list max-height="320" max-width="420" density="compact">
            <v-list-subheader>System Fields</v-list-subheader>

            <v-list-item
              v-for="field in getSystemFields(event.key)"
              :key="field"
              :title="field"
              @click="insertField(event.key, field)" />

            <v-list-subheader>Custom Project Arguments</v-list-subheader>

            <template v-for="name in arrKey" :key="name">
              <v-list-item @click="insertArgument(event.key, name, true)">
                <template #title>
                  <span class="text-info">Input :</span>
                  {{ name }}
                </template>
              </v-list-item>

              <v-list-item
                v-if="event.key !== 'on_start'"
                @click="insertArgument(event.key, name, false)">
                <template #title>
                  <span class="text-secondary">Output:</span>
                  {{ name }}
                </template>
              </v-list-item>
            </template>
          </v-list>
        </v-menu>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { getApiError, getFieldErrors } from "@/api/errors";
import { getRunEmailRecipients, type RunEmailRecipient } from "@/api/runEmail";
import type { RunEmailConfig } from "@/api/runSettings";

const props = defineProps<{
  argumentKeys: string[];
  disabled?: boolean;
  readonly?: boolean;
  fieldErrors?: Record<string, string[]>;
}>();

const config = defineModel<RunEmailConfig>({ required: true });

type EventKey = "on_start" | "on_completed" | "on_error";

const ARR_EVENT: { key: EventKey; title: string }[] = [
  { key: "on_start", title: "On Start" },
  { key: "on_completed", title: "On End (Completed)" },
  { key: "on_error", title: "On End (Error)" },
];

const ARR_SYSTEM_FIELD = [
  "organization_name",
  "department_name",
  "project_name",
  "project_version",
  "trigger_source",
  "schedule_name",
  "scheduled_at",
  "executor_name",
  "computer_name",
  "account_name",
  "python_environment_name",
  "started_at",
  "job_id",
  "run_id",
  "details_url",
];

const arrKey = computed(() => [...new Set(props.argumentKeys)]);
const arrOpenPanel = ref<EventKey[]>([]);
const arrRecipient = ref<RunEmailRecipient[]>([]);
const strError = ref("");

const fieldByEvent = ref<Record<EventKey, "subject" | "body">>({
  on_start: "body",
  on_completed: "body",
  on_error: "body",
});

function getSystemFields(event: EventKey): string[] {
  return [
    ...ARR_SYSTEM_FIELD,
    ...(event === "on_start" ? [] : ["ended_at", "elapsed_seconds"]),
    ...(event === "on_error" ? ["error_type", "error_message"] : []),
  ];
}

function setField(event: EventKey, field: "subject" | "body"): void {
  fieldByEvent.value[event] = field;
}

function insertField(event: EventKey, field: string): void {
  config.value[event][fieldByEvent.value[event]] += `{{${field}}}`;
}

function insertArgument(event: EventKey, name: string, input: boolean): void {
  const strHex = Array.from(new TextEncoder().encode(name), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
  insertField(event, `${input ? "Input_CustomArgs_" : "CustomArgs_"}${strHex}`);
}

watch(
  () => props.fieldErrors,
  (fields) => {
    for (const event of ARR_EVENT)
      if (
        getFieldErrors(fields, `settings.run_email.${event.key}`).length &&
        !arrOpenPanel.value.includes(event.key)
      )
        arrOpenPanel.value.push(event.key);
  },
);

onMounted(async () => {
  try {
    arrRecipient.value = (await getRunEmailRecipients()).recipients;
  } catch (e) {
    strError.value = getApiError(e).message;
  }
});
</script>

<style scoped></style>
