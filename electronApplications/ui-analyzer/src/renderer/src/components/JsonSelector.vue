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
          @click="void copyJsonToClipboard()">
          Copy
          <v-tooltip activator="parent" location="top"> Copy the JSON Selector. </v-tooltip>
        </v-btn>

        <v-btn
          class="mr-2"
          prepend-icon="mdi-content-paste"
          variant="tonal"
          @click="void pasteFromClipboard()">
          Paste
          <v-tooltip activator="parent" location="top">
            Paste clipboard content into JSON Selector.
          </v-tooltip>
        </v-btn>
      </v-col>
    </v-row>

    <!-- Use a native textarea because v-textarea has layout issues here. -->
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
import { parseSelectorJsonText } from "../attrHandleFunc";
import { useSelectorStore } from "../store";

const selectorStore = useSelectorStore();

const strInfoText = ref("Have no JSON Selector.");
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
    strInfoText.value = "Have no JSON Selector.";
    booleanJsonParse.value = true;
    return;
  }

  const dictParseResult = parseSelectorJsonText(selectorStore.strJsonText);

  if (dictParseResult.success) {
    strInfoText.value =
      dictParseResult.mode === "json"
        ? "JSON syntax is correct."
        : "JSON-like selector syntax is correct. Trailing commas are accepted.";

    booleanJsonParse.value = true;
    return;
  }

  strInfoText.value = dictParseResult.errorMessage;
  booleanJsonParse.value = false;
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
