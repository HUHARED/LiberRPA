<!-- FileName: ButtonArea.vue -->
<template>
  <v-container fluid class="pa-2 ma-0" style="height: 70px">
    <v-label class="area-header">Operation Buttons</v-label>
    <v-row class="w-100">
      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-monitor"
          density="compact"
          variant="tonal"
          :disabled="operationStore.isBusy"
          @click="indicateUia()">
          uia
          <v-tooltip activator="parent" location="bottom">
            Indicate a UIA element on the screen.
          </v-tooltip>
        </v-btn>
      </v-col>

      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-web"
          density="compact"
          variant="tonal"
          :disabled="operationStore.isBusy"
          @click="indicateChrome()">
          html
          <v-tooltip activator="parent" location="bottom">
            <div>
              Indicate an HTML element in the active tab.<br />
              Currently only Chrome is supported. The target must be in the last focused
              tab.
            </div>
          </v-tooltip>
        </v-btn>
      </v-col>

      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-image-search-outline"
          density="compact"
          variant="tonal"
          :disabled="operationStore.isBusy"
          @click="indicateImage()">
          image
          <v-tooltip activator="parent" location="bottom">
            Indicate an image element on the screen.
          </v-tooltip>
        </v-btn>
      </v-col>

      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-window-restore"
          density="compact"
          variant="tonal"
          :disabled="operationStore.isBusy"
          @click="indicateWindow()">
          window
          <v-tooltip activator="parent" location="bottom">
            <div>
              Indicate a window element on the screen.<br />
              It is also a top-level UIA element.
            </div>
          </v-tooltip>
        </v-btn>
      </v-col>

      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-search-web"
          density="compact"
          :color="informationStore.updateValidateColor()"
          variant="tonal"
          :disabled="operationStore.isBusy"
          @click="validateSelector()">
          Validate
          <v-tooltip activator="parent" location="bottom">
            Validate the current JSON Selector by locating the target element.
          </v-tooltip>
        </v-btn>
      </v-col>

      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-refresh"
          density="compact"
          variant="tonal"
          :disabled="operationStore.isBusy"
          @click="resetUI()">
          Reset
          <v-tooltip activator="parent" location="bottom">
            Clear the current selector data and reset the UI.
          </v-tooltip>
        </v-btn>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { startUiAnalyzerOperation } from "../ipcOfRenderer";
import { parseSelectorJsonText } from "../attrHandleFunc";
import {
  useInformationStore,
  useOperationStore,
  useSelectorStore,
  useSettingStore,
} from "../store";

const selectorStore = useSelectorStore();
const settingStore = useSettingStore();
const informationStore = useInformationStore();
const operationStore = useOperationStore();

async function indicateUia(): Promise<void> {
  await startUiAnalyzerOperation("indicate_uia", {
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
  });
}

async function indicateChrome(): Promise<void> {
  await startUiAnalyzerOperation("indicate_chrome", {
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
    usePath: settingStore.indexOrPath === "path",
  });
}

async function indicateImage(): Promise<void> {
  await startUiAnalyzerOperation(
    "indicate_image",
    {
      intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
      grayscale: settingStore.grayscale,
      confidence: settingStore.confidence,
    },
    {
      // The Qt screenshot window would also be minimized.
      minimizeWindow: false,
    },
  );
}

async function indicateWindow(): Promise<void> {
  await startUiAnalyzerOperation("indicate_window", {
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
  });
}

async function validateSelector(): Promise<void> {
  informationStore.resetSelectorValidation();

  const strSelectorText = selectorStore.strJsonText;
  const dictParseResult = parseSelectorJsonText(strSelectorText);

  if (!dictParseResult.success) {
    informationStore.showAlertMessage(dictParseResult.errorMessage);
    return;
  }

  await startUiAnalyzerOperation(
    "validate",
    {
      intMatchTimeoutSeconds: settingStore.intMatchTimeoutSeconds,
      selector: dictParseResult.data,
    },
    {
      validateSelectorText: strSelectorText,
    },
  );
}

function resetUI(): void {
  if (operationStore.isBusy) return;

  // Clean Element Hierarchy, Json Selector, Attribute Editor.
  selectorStore.$reset();
  informationStore.$reset();

  settingStore.leftColumnWidth = 250;
  settingStore.rightColumnWidth = 250;
}
</script>

<style scoped>
.v-btn {
  width: 120px;
  padding: 0px;
}
</style>
