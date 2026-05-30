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
          @click="void indicateUia()">
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
          @click="void indicateChrome()">
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
          @click="void indicateWindow()">
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
          @click="void validateSelector()">
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
import { sendCmdToFlask } from "../ipcOfRenderer";
import { parseSelectorJsonText } from "../attrHandleFunc";
import { useSelectorStore, useSettingStore, useInformationStore } from "../store";

const selectorStore = useSelectorStore();
const settingStore = useSettingStore();
const informationStore = useInformationStore();

async function indicateUia(): Promise<void> {
  await settingStore.toggleWindow();
  sendCmdToFlask({
    commandName: "indicate_uia",
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
  });
  selectorStore.setDescription("Indicating UIA element.");
}

async function indicateChrome(): Promise<void> {
  await settingStore.toggleWindow();
  sendCmdToFlask({
    commandName: "indicate_chrome",
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
    usePath: settingStore.indexOrPath === "path",
  });
  selectorStore.setDescription("Indicating Chrome element.");
}

function indicateImage(): void {
  // settingStore.toggleWindow(); Not minimize the UI Analyzer window, because the QT window will also be minimized.
  settingStore.boolIndicateImage = true;

  sendCmdToFlask({
    commandName: "indicate_image",
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
    grayscale: settingStore.grayscale,
    confidence: settingStore.confidence,
  });
  selectorStore.setDescription("Indicating image element.");
}

async function indicateWindow(): Promise<void> {
  await settingStore.toggleWindow();
  sendCmdToFlask({
    commandName: "indicate_window",
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
  });
  selectorStore.setDescription("Indicating window element.");
}

async function validateSelector(): Promise<void> {
  const dictParseResult = parseSelectorJsonText(selectorStore.strJsonText);

  if (!dictParseResult.success) {
    informationStore.showAlertMessage(dictParseResult.errorMessage);
    return;
  }

  await settingStore.toggleWindow();

  sendCmdToFlask({
    commandName: "validate",
    intMatchTimeoutSeconds: settingStore.intMatchTimeoutSeconds,
    strSelectorJson: dictParseResult.data,
  });
  selectorStore.setDescription("Validating element.");
}

function resetUI(): void {
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
