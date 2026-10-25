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
    :variant="readonly ? 'plain' : 'underlined'"
    :menu-icon="readonly ? '' : undefined"
    :items="arrRecipient"
    item-title="email"
    item-value="id"
    label="To (up to 5)"
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
          true-icon="mdi-email-outline"
          :disabled="disabled"
          :readonly="readonly" />

        <v-text-field
          :model-value="draft[event.key].subject"
          :variant="readonly ? 'plain' : 'underlined'"
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
          :id="`${strEditorId}-${event.key}-body`"
          :model-value="draft[event.key].body"
          :variant="readonly ? 'plain' : 'underlined'"
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
import { computed, nextTick, onMounted, ref, useId, watch } from "vue";

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
const strEditorId = useId();

const ARR_EVENT: { key: RunEmailEventKey; title: string }[] = [
  { key: "on_start", title: "On Start" },
  { key: "on_completed", title: "On End (Completed)" },
  { key: "on_error", title: "On End (Error / Timeout)" },
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
  if (props.readonly || props.disabled || !defaultTemplates.value) return;

  const selection = selectionByEvent[event];
  const target = selection?.field ?? "body";
  const element =
    selection?.element ?? document.getElementById(`${strEditorId}-${event}-body`);
  if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement))
    return;

  const intStart = selection?.start ?? element.value.length;
  const intEnd = selection?.end ?? element.value.length;
  const strPlaceholder = `{{${field}}}`;
  const intScrollTop = element.scrollTop;

  element.focus({ preventScroll: true });
  element.setSelectionRange(intStart, intEnd);

  // NOTE: Deprecated insertText preserves native undo history; setRangeText does not.
  if (!document.execCommand("insertText", false, strPlaceholder)) {
    element.setRangeText(strPlaceholder, intStart, intEnd, "end");
  }
  setTemplate(event, target, element.value);

  await nextTick();
  const intCaret = intStart + strPlaceholder.length;
  element.focus({ preventScroll: true });
  element.setSelectionRange(intCaret, intCaret);
  element.scrollTop = intScrollTop;
  selectionByEvent[event] = { field: target, element, start: intCaret, end: intCaret };
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
