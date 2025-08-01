<!-- FileName: JsonSelector.vue -->
<template>
  <v-container class="clean-space flex-column" style="height: 350px">
    <v-label class="area-header"> Json Selector </v-label>

    <v-row class="clean-space" style="max-height: 40px">
      <!-- Information text -->
      <v-col cols="8" class="clean-space">
        <v-text-field
          v-model="strInfoText"
          class="clean-space"
          density="compact"
          hide-details
          readonly
          variant="plain">
          <template #prepend-inner>
            <v-icon
              :color="booleanJsonParse ? 'info' : 'error'"
              :icon="booleanJsonParse ? 'mdi-dots-horizontal' : 'mdi-alert-box-outline'" />
          </template>

          <v-tooltip activator="parent" location="top">
            {{ strInfoText }}
          </v-tooltip>
        </v-text-field>
      </v-col>

      <!-- Grouped Buttons Column, aligned right -->
      <v-col cols="4" class="clean-space d-flex justify-end">
        <v-btn
          class="mr-2"
          prepend-icon="mdi-content-copy"
          variant="tonal"
          @click="copyJsonToClipboard">
          Copy
          <v-tooltip activator="parent" location="top"> Copy the JSON Selector </v-tooltip>
        </v-btn>

        <v-btn
          class="mr-2"
          prepend-icon="mdi-content-paste"
          variant="tonal"
          @click="pasteFromClipboard">
          Paste
          <v-tooltip activator="parent" location="top">
            Paste the content in clipboard in JSON Selector
          </v-tooltip>
        </v-btn>
      </v-col>
    </v-row>

    <!-- v-textarea has some wrong in layout, so use textarea. -->
    <textarea
      v-model="selectorStore.strJsonText"
      class="ma-1 flex-column-grow-1"
      spellcheck="false">
    </textarea>
  </v-container>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { debounce } from "lodash";

import { loggerRenderer } from "../ipcOfRenderer";
import { fixTrailingCommas } from "../attrHandleFunc";
import { useSelectorStore } from "../store";

const selectorStore = useSelectorStore();

const strInfoText = ref("Have no Json Selector.");
const booleanJsonParse = ref(true);

watch(
  () => selectorStore.strJsonText,
  () => {
    validateJson();
  }
);

// Update selectorStore.strJsonText when selectorStore.arrEleHierarchy is modified.
const debounced_Update = debounce(() => {
  if (selectorStore.arrEleHierarchy.length !== 0) {
    selectorStore.updateCheckedLayerAndJsonText();
  }
}, 300);

watch(
  () => selectorStore.arrEleHierarchy,
  () => {
    debounced_Update();
  },
  { deep: true }
);

function validateJson(): void {
  if (!selectorStore.strJsonText.trim()) {
    strInfoText.value = "Have no Json Selector.";
    booleanJsonParse.value = true;
    return;
  }

  try {
    JSON.parse(selectorStore.strJsonText);
    strInfoText.value = "JSON syntax is correct.";
    booleanJsonParse.value = true;
  } catch (error) {
    // Asserting error as an instance of Error
    const message = error instanceof Error ? error.message : "Unknown error";

    // If it's Black format, don't treat as error.
    if (message.startsWith("Expected double-quoted property name in JSON at position")) {
      try {
        JSON.parse(fixTrailingCommas(selectorStore.strJsonText));
        strInfoText.value = "It's a correct Python dictionary.";
        booleanJsonParse.value = true;
      } catch (e) {
        strInfoText.value = `Syntax error: ${message}`;
        booleanJsonParse.value = false;
      }
    } else {
      strInfoText.value = `Syntax error: ${message}`;
      booleanJsonParse.value = false;
    }
  }
}

async function copyJsonToClipboard(): Promise<void> {
  try {
    await navigator.clipboard.writeText(selectorStore.strJsonText);
    loggerRenderer.debug("JSON copied to clipboard:\n" + selectorStore.strJsonText);
  } catch (error) {
    loggerRenderer.error("Failed to copy: " + String(error));
  }
}

async function pasteFromClipboard(): Promise<void> {
  try {
    const text = await navigator.clipboard.readText();
    selectorStore.strJsonText = text;
    loggerRenderer.debug("Pasted content from clipboard:\n" + selectorStore.strJsonText);
  } catch (error) {
    loggerRenderer.error("Failed to paste: " + String(error));
  }
}
</script>

<style scoped></style>
