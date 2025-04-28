<!-- FileName: ButtonArea.vue -->
<template>
  <v-container fluid class="pa-2 ma-0" style="height: 70px">
    <v-label class="header-label">Operation Buttons</v-label>
    <v-row class="w-100">
      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-monitor"
          density="compact"
          variant="tonal"
          @click="indicateUia()">
          uia
          <v-tooltip activator="parent" location="bottom">
            Indicate an uia element in the screen.
          </v-tooltip>
        </v-btn>
      </v-col>

      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-web"
          density="compact"
          variant="tonal"
          @click="indicateChrome()">
          html
          <v-tooltip activator="parent" location="bottom">
            Indicate an html element in the actived tab. (Only support Chrome now.)
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
            Indicate an image element in the screen.
          </v-tooltip>
        </v-btn>
      </v-col>

      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-window-restore"
          density="compact"
          variant="tonal"
          @click="indicateWindow()">
          window
          <v-tooltip activator="parent" location="bottom">
            Indicate a window element in the screen. (It is also top-level uia element)
          </v-tooltip>
        </v-btn>
      </v-col>

      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-search-web"
          density="compact"
          :color="informationStore.updateValidateColor()"
          variant="tonal"
          @click="validateSelector()">
          Validate
          <v-tooltip activator="parent" location="bottom">
            Try to find the element that defined by Json Selector.
          </v-tooltip>
        </v-btn>
      </v-col>

      <v-col cols="auto">
        <v-btn
          prepend-icon="mdi-refresh"
          density="compact"
          variant="tonal"
          @click="reset()">
          Reset
          <v-tooltip activator="parent" location="bottom">
            Clean the element and reset the GUI.
          </v-tooltip>
        </v-btn>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { sendCmdToFlask } from "../ipcOfRenderer";
import { fixTrailingCommas } from "../attrHandleFunc";
import { useSelectorStore, useSettingStore, useInformationStore } from "../store";

const selectorStore = useSelectorStore();
const settingStore = useSettingStore();
const informationStore = useInformationStore();

function indicateUia(): void {
  settingStore.toggleWindow();
  sendCmdToFlask({
    commandName: "indicate_uia",
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
  });
  selectorStore.setDescription("Indicating uia.");
  informationStore.$reset();
}

function indicateChrome(): void {
  settingStore.toggleWindow();
  sendCmdToFlask({
    commandName: "indicate_chrome",
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
    usePath: settingStore.indexOrPath === "path" ? true : false,
  });
  selectorStore.setDescription("Indicating Chrome.");
  informationStore.$reset();
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
  selectorStore.setDescription("Indicating image.");
  informationStore.$reset();
}

function indicateWindow(): void {
  settingStore.toggleWindow();
  sendCmdToFlask({
    commandName: "indicate_window",
    intIndicateDelaySeconds: settingStore.intIndicateDelaySeconds,
  });
  selectorStore.setDescription("Indicating window.");
  informationStore.$reset();
}

function validateSelector(): void {
  settingStore.toggleWindow();

  sendCmdToFlask({
    commandName: "validate",
    intMatchTimeoutSeconds: settingStore.intMatchTimeoutSeconds,
    strSelectorJson: JSON.parse(fixTrailingCommas(selectorStore.strJsonText)),
  });
  selectorStore.setDescription("Validate element.");
  informationStore.$reset();
}

function reset(): void {
  // Clean Element Hierarchy, Json Selector, Attribute Editor.
  selectorStore.$reset();
  // selectorStore.arrEleHierarchy = [];
  informationStore.validateState = undefined;
  settingStore.leftColumnWidth = 250;
  settingStore.rightColumnWidth = 250;

  informationStore.previewImage = "";
  informationStore.information = "...";
  selectorStore.processDescription = "Idle";
}
</script>

<style scoped>
.v-btn {
  width: 120px;
  padding: 0px;
}
</style>
