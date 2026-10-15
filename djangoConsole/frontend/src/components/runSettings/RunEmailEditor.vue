<!-- FileName: RunEmailEditor.vue -->
<template>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-3">
    {{ strError }}
    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      size="small"
      class="ml-3"
      :loading="boolLoading"
      @click="loadOptions">
      Retry
    </v-btn>
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
        {{ event.title }}
        <v-chip
          :border="`${config[event.key].enabled ? 'success' : 'inactive'} thin opacity-25`"
          :color="config[event.key].enabled ? 'success' : 'inactive'"
          :text="config[event.key].enabled ? 'Enabled' : 'Disabled'"
          variant="text"
          size="x-small"
          class="ml-3" />
      </v-expansion-panel-title>

      <v-expansion-panel-text eager>
        <v-switch
          v-model="config[event.key].enabled"
          :error-messages="
            getFieldErrors(fieldErrors, `settings.run_email.${event.key}.enabled`)
          "
          :label="event.title"
          :disabled="disabled"
          :readonly="readonly" />

        <v-text-field
          :model-value="draft[event.key].subject"
          variant="underlined"
          :error-messages="
            getFieldErrors(fieldErrors, `settings.run_email.${event.key}.subject`)
          "
          label="Subject"
          hint="Leave empty to use the default template."
          :disabled="disabled || !defaultTemplates"
          :readonly="readonly"
          @focus="rememberSelection(event.key, 'subject', $event)"
          @blur="rememberSelection(event.key, 'subject', $event)"
          @update:model-value="setTemplate(event.key, 'subject', $event)" />

        <v-textarea
          :model-value="draft[event.key].body"
          variant="underlined"
          :error-messages="
            getFieldErrors(fieldErrors, `settings.run_email.${event.key}.body`)
          "
          label="Body (plain text)"
          rows="5"
          hint="Leave empty to use the default template."
          :disabled="disabled || !defaultTemplates"
          :readonly="readonly"
          @focus="rememberSelection(event.key, 'body', $event)"
          @blur="rememberSelection(event.key, 'body', $event)"
          @update:model-value="setTemplate(event.key, 'body', $event)" />

        <v-menu v-if="!readonly">
          <template #activator="{ props: menuProps }">
            <v-btn
              v-bind="menuProps"
              variant="tonal"
              prepend-icon="mdi-code-braces"
              :disabled="disabled || !defaultTemplates">
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
import { computed, nextTick, onMounted, ref, watch } from "vue";

import { getApiError, getFieldErrors } from "@/api/errors";
import {
  getRunEmailRecipients,
  getRunEmailTemplates,
  type RunEmailRecipient,
  type RunEmailEventKey,
  type RunEmailTemplates,
} from "@/api/runEmail";
import type { RunEmailConfig } from "@/api/runSettings";

interface TemplateSelection {
  field: "subject" | "body";
  element: HTMLInputElement | HTMLTextAreaElement;
  start: number;
  end: number;
}

const props = defineProps<{
  argumentKeys: string[];
  disabled?: boolean;
  readonly?: boolean;
  fieldErrors?: Record<string, string[]>;
}>();

const config = defineModel<RunEmailConfig>({ required: true });

const ARR_EVENT: { key: RunEmailEventKey; title: string }[] = [
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
const arrOpenPanel = ref<RunEmailEventKey[]>([]);
const arrRecipient = ref<RunEmailRecipient[]>([]);
const strError = ref("");
const boolLoading = ref(false);
const defaultTemplates = ref<RunEmailTemplates | null>(null);

const draft = ref<RunEmailTemplates>({
  on_start: { subject: config.value.on_start.subject, body: config.value.on_start.body },
  on_completed: {
    subject: config.value.on_completed.subject,
    body: config.value.on_completed.body,
  },
  on_error: { subject: config.value.on_error.subject, body: config.value.on_error.body },
});

const selectionByEvent: Partial<Record<RunEmailEventKey, TemplateSelection>> = {};

function getSystemFields(event: RunEmailEventKey): string[] {
  return [
    ...ARR_SYSTEM_FIELD,
    ...(event === "on_start" ? [] : ["ended_at", "elapsed_seconds"]),
    ...(event === "on_error" ? ["error_type", "error_message"] : []),
  ];
}

function rememberSelection(
  event: RunEmailEventKey,
  field: "subject" | "body",
  focusEvent: FocusEvent,
): void {
  const element = focusEvent.target;
  if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement))
    return;
  selectionByEvent[event] = {
    field,
    element,
    start: element.selectionStart ?? element.value.length,
    end: element.selectionEnd ?? element.value.length,
  };
}

function setTemplate(
  event: RunEmailEventKey,
  field: "subject" | "body",
  value: string,
): void {
  if (props.readonly || props.disabled || !defaultTemplates.value) return;
  draft.value[event][field] = value;
  config.value[event][field] = value;
}

async function insertField(event: RunEmailEventKey, field: string): Promise<void> {
  const selection = selectionByEvent[event];
  const target = selection?.field ?? "body";
  const strText = draft.value[event][target];
  const intStart = selection?.start ?? strText.length;
  const intEnd = selection?.end ?? strText.length;
  const strPlaceholder = `{{${field}}}`;
  setTemplate(
    event,
    target,
    strText.slice(0, intStart) + strPlaceholder + strText.slice(intEnd),
  );

  if (selection) {
    await nextTick();
    const intCaret = intStart + strPlaceholder.length;
    selection.element.focus();
    selection.element.setSelectionRange(intCaret, intCaret);
    selectionByEvent[event] = { ...selection, start: intCaret, end: intCaret };
  }
}

function insertArgument(event: RunEmailEventKey, name: string, input: boolean): void {
  void insertField(
    event,
    `${input ? "Input_CustomArgs" : "Output_CustomArgs"}[${JSON.stringify(name)}]`,
  );
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

// Defaults are display drafts; loading them must not change the saved configuration.
watch([() => config.value, defaultTemplates], () => {
  for (const { key } of ARR_EVENT) {
    delete selectionByEvent[key];
    draft.value[key] = {
      subject: config.value[key].subject || defaultTemplates.value?.[key].subject || "",
      body: config.value[key].body || defaultTemplates.value?.[key].body || "",
    };
  }
});

async function loadOptions(): Promise<void> {
  if (boolLoading.value) return;
  boolLoading.value = true;
  strError.value = "";
  try {
    const [recipients, templates] = await Promise.all([
      getRunEmailRecipients(),
      getRunEmailTemplates(),
    ]);
    arrRecipient.value = recipients.recipients;
    defaultTemplates.value = templates;
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolLoading.value = false;
  }
}

onMounted(() => void loadOptions());
</script>

<style scoped></style>
