<!-- FileName: App.vue -->
<template>
  <v-app
    v-if="boolLoaded"
    class="pa-0 ma-0 fill-height overflow-y-hidden"
    :theme="settingStore.theme"
    @keydown="handleKeydown">
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
        style="width: 0px; cursor: col-resize"
        @mousedown="startResizing"></div>

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
        <BuiltInPrjArgs />
        <!-- Give it a fixed height, otherwise the overflow-y-auto of argument list will never work. Why? -->
        <CustomPrjArgs class="flex-grow-1" style="height: 100px" />
      </div>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref, onBeforeMount, onUnmounted } from "vue";
import FlowchartArea from "./components/FlowchartArea.vue";
import NodePanel from "./components/NodePanel.vue";
import NodeInfo from "./components/NodeInfo.vue";
import SettingArea from "./components/SettingArea.vue";
import BuiltInPrjArgs from "./components/BuiltinPrjArgs.vue";
import CustomPrjArgs from "./components/CustomPrjArgs.vue";
import Alert from "./components/Alert.vue";
import { useFlowchartStore, useSettingStore, useArgsStore } from "./store";
import type { DictProject, ExtensionToWebviewMessage, Theme } from "./interface";
import { initDictFinal, notifyWebviewReady, requestWorkspaceSearch } from "./commonFunc";

const flowchartStore = useFlowchartStore();
const settingStore = useSettingStore();
const argsStore = useArgsStore();

const boolLoaded = ref(false);

onUnmounted(() => {
  window.removeEventListener("message", handleMessage);
});

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isTheme(value: unknown): value is Theme {
  return value === "light" || value === "dark";
}

function isExtensionToWebviewMessage(value: unknown): value is ExtensionToWebviewMessage {
  if (!isRecord(value) || typeof value.command !== "string") {
    return false;
  }

  switch (value.command) {
    case "load":
      return isRecord(value.data);

    case "themeChanged":
      return isTheme(value.theme);

    default:
      return false;
  }
}

function handleMessage(event: MessageEvent): void {
  const message: unknown = event.data;

  if (!isExtensionToWebviewMessage(message)) {
    console.warn("Ignored invalid extension message:", message);
    return;
  }

  switch (message.command) {
    case "load": {
      const dictVscodeData = message.data;

      const dictProject: DictProject = {
        nodes: dictVscodeData.nodes,
        edges: dictVscodeData.edges,
        executeMode: dictVscodeData.executeMode,
        logLevel: dictVscodeData.logLevel,
        recordVideo: dictVscodeData.recordVideo,
        stopShortcut: dictVscodeData.stopShortcut,
        highlightUi: dictVscodeData.highlightUi,
        customPrjArgs: dictVscodeData.customPrjArgs,
      };

      flowchartStore.data = {
        nodes: dictProject.nodes,
        edges: dictProject.edges,
      };

      settingStore.executeMode = dictProject.executeMode;
      argsStore.logLevel = dictProject.logLevel;
      argsStore.recordVideo = dictProject.recordVideo;
      argsStore.stopShortcut = dictProject.stopShortcut;
      argsStore.highlightUi = dictProject.highlightUi;
      argsStore.customPrjArgs = dictProject.customPrjArgs;

      settingStore.theme = dictVscodeData.theme;

      initDictFinal(dictProject);

      boolLoaded.value = true;
      break;
    }

    case "themeChanged": {
      settingStore.theme = message.theme;
      break;
    }

    default:
      break;
  }
}

onBeforeMount(() => {
  window.addEventListener("message", handleMessage);

  // Tell the extension that the webview is ready to receive the initial data.
  notifyWebviewReady();
});

const intRightColumnWidth = ref(300);
let intStartX = 0;
let intStartWidth = 0;
let boolResizing = false;

function startResizing(event: MouseEvent): void {
  // Prevent text selection.
  event.preventDefault();
  window.getSelection()?.removeAllRanges();

  boolResizing = true;
  intStartX = event.clientX;
  intStartWidth = intRightColumnWidth.value;

  document.body.classList.add("is-column-resizing");

  window.addEventListener("mousemove", mouseMoveHandler);
  window.addEventListener("mouseup", stopResizing);
}

function mouseMoveHandler(event: MouseEvent): void {
  if (!boolResizing) return;

  event.preventDefault();

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
  boolResizing = false;

  document.body.classList.remove("is-column-resizing");
  window.getSelection()?.removeAllRanges();

  window.removeEventListener("mousemove", mouseMoveHandler);
  window.removeEventListener("mouseup", stopResizing);
}

function getSelectedText(): string | undefined {
  const activeElement = document.activeElement;

  if (
    activeElement instanceof HTMLInputElement ||
    activeElement instanceof HTMLTextAreaElement
  ) {
    const intSelectionStart = activeElement.selectionStart;
    const intSelectionEnd = activeElement.selectionEnd;

    if (
      intSelectionStart !== null &&
      intSelectionEnd !== null &&
      intSelectionStart !== intSelectionEnd
    ) {
      return activeElement.value.slice(intSelectionStart, intSelectionEnd);
    }

    return undefined;
  }

  const strSelectedText = window.getSelection()?.toString();
  return strSelectedText ? strSelectedText : undefined;
}

function handleWorkspaceSearchShortcut(event: KeyboardEvent): boolean {
  if (!(event.ctrlKey || event.metaKey) || !event.shiftKey || event.altKey) {
    return false;
  }

  const strKey = event.key.toLowerCase();
  if (strKey !== "f" && strKey !== "h") {
    return false;
  }

  event.preventDefault();
  event.stopPropagation();

  requestWorkspaceSearch(strKey === "f" ? "find" : "replace", getSelectedText());
  return true;
}

// Handle keydown events and prevent VS Code from intercepting Webview shortcuts.
function handleKeydown(event: KeyboardEvent): void {
  if (handleWorkspaceSearchShortcut(event)) {
    return;
  }

  // Check if Ctrl + Z or Ctrl + Y is pressed
  if ((event.ctrlKey || event.metaKey) && (event.key === "z" || event.key === "y")) {
    // Prevent the event from bubbling up to VS Code
    event.stopPropagation();
  }
}
</script>

<style scoped>
:global(body.is-column-resizing *) {
  /* Keep the resize cursor visible while dragging outside the divider */
  cursor: col-resize !important;
}
</style>
