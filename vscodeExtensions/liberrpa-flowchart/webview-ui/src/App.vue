<!-- FileName: App.vue -->
<template>
  <v-app
    v-if="boolLoaded"
    @keydown="handleKeydown"
    class="pa-0 ma-0 fill-height overflow-y-hidden"
    :theme="settingStore.theme">
    <v-main class="pa-0 ma-0 fill-height d-flex">
      <Alert style="position: fixed; width: 100%; opacity: 0.9; z-index: 999" />
      <!-- Left column -->
      <v-container
        class="pa-0 ma-0 fill-height d-flex flex-column"
        style="min-width: 150px; width: 150px">
        <NodePanel />
        <NodeInfo />
      </v-container>

      <!-- Divider -->
      <div class="pa-0 ma-0 fill-height border-thin" style="width: 0px"></div>

      <!-- Middle column -->
      <v-container
        class="pa-0 ma-0 fill-height flex-grow-1"
        style="flex-shrink: 1; min-width: 0px">
        <FlowchartArea />
      </v-container>

      <!-- Divider -->
      <div
        class="pa-0 ma-0 fill-height border-thin"
        @mousedown="startResizing"
        style="width: 0px; cursor: col-resize"></div>

      <!-- Right column -->
      <div
        class="pa-0 ma-0 fill-height d-flex flex-column"
        :style="{
          width: intRightColumnWidth + 'px',
          minWidth: '300px',
          maxWidth: '900px',
          flexShrink: '0',
        }">
        <SettingArea />
        <BuildinPrjArgs />
        <!-- Give it a fixed height, otherwise the overflow-y-auto of argument list will never work. Why? -->
        <CustomPrjArgs class="flex-grow-1" style="height: 100px" />
      </div>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref, onBeforeMount } from "vue";
import FlowchartArea from "./components/FlowchartArea.vue";
import NodePanel from "./components/NodePanel.vue";
import NodeInfo from "./components/NodeInfo.vue";
import SettingArea from "./components/SettingArea.vue";
import BuildinPrjArgs from "./components/BuildinPrjArgs.vue";
import CustomPrjArgs from "./components/CustomPrjArgs.vue";
import Alert from "./components/Alert.vue";
import { useFlowchartStore, useSettingStore, useArgsStore } from "./store";
import { DictProject } from "./interface";
import { initDictFinal } from "./commonFunc";

const flowchartStore = useFlowchartStore();
const settingStore = useSettingStore();
const argsStore = useArgsStore();

const boolLoaded = ref(false);

onBeforeMount(() => {
  window.addEventListener("message", (event) => {
    console.log("event", event);

    const message = event.data;
    switch (message.command) {
      case "load":
        console.log(message.data);

        // const dictVscodeData = JSON.parse(message.data) as DictProject;
        const dictVscodeData = message.data as DictProject;

        flowchartStore.data = {
          nodes: dictVscodeData.nodes,
          edges: dictVscodeData.edges,
        };
        settingStore.executeMode = dictVscodeData.executeMode;
        argsStore.logLevel = dictVscodeData.logLevel;
        argsStore.recordVideo = dictVscodeData.recordVideo;
        argsStore.stopShortcut = dictVscodeData.stopShortcut;
        argsStore.highlightUi = dictVscodeData.highlightUi;
        argsStore.customPrjArgs = dictVscodeData.customPrjArgs;
        if (dictVscodeData.theme) {
          settingStore.theme = dictVscodeData.theme;
        }

        delete dictVscodeData.theme;
        initDictFinal(dictVscodeData);

        boolLoaded.value = true;
        break;

      default:
        break;
    }
  });
});

const intRightColumnWidth = ref(300);
let intStartX = 0;
let intStartWidth = 0;
let boolResizing = false;

function startResizing(event: MouseEvent): void {
  boolResizing = true;
  intStartX = event.clientX;
  intStartWidth = intRightColumnWidth.value;

  window.addEventListener("mousemove", mouseMoveHandler);
  window.addEventListener("mouseup", stopResizing);
}

function mouseMoveHandler(event: MouseEvent): void {
  if (!boolResizing) return;
  const intDistanceX = event.clientX - intStartX;

  let intNewWidth = intStartWidth - intDistanceX;
  // Ensure the new width is within the allowed range
  intNewWidth = Math.max(300, Math.min(900, intNewWidth));
  // Round the new width to the nearest 50px
  intNewWidth = Math.round(intNewWidth / 50) * 50;

  intRightColumnWidth.value = intNewWidth;
  // console.log(rightColumnWidth.value);
}

function stopResizing(): void {
  // console.log("stop");
  boolResizing = false;
  window.removeEventListener("mousemove", mouseMoveHandler);
  window.removeEventListener("mouseup", stopResizing);
}

// Handle keydown events and prevent VS Code from intercepting
function handleKeydown(event: KeyboardEvent) {
  // Check if Ctrl + Z or Ctrl + Y is pressed
  if (
    (event.ctrlKey || event.metaKey) &&
    (event.key === "z" || event.key === "y")
  ) {
    // Prevent the event from bubbling up to VS Code
    event.stopPropagation();
  }
}
</script>

<style scoped></style>
