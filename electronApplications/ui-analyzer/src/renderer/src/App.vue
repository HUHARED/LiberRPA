<!-- FileName: App.vue -->
<template>
  <v-app class="clean-space" style="height: 100vh" :theme="settingStore.theme">
    <!-- The Alert area, doesn't join in layout -->
    <Alert />
    <SocketState />

    <v-main class="clean-space fill-height">
      <v-container class="clean-space fill-height flex-column" fluid>
        <!-- Head Area for Button -->
        <ButtonArea />

        <!-- Divider for Head Area, can't drag -->
        <div class="clean-space border-thin" style="height: 0px; width: 100%"></div>

        <!-- The Main Area, including 3 columns content -->
        <v-container class="clean-space flex-row flex-column-grow-1" fluid>
          <!-- Left Column -->
          <!-- Use :style to implement divider deag feature -->
          <v-container
            id="left-column"
            class="clean-space fill-height flex-column"
            :style="{
              width: settingStore.leftColumnWidth + 'px',
              minWidth: '250px',
              maxWidth: '750px',
              flexShrink: '0',
            }">
            <ElementTree />
            <PreviewImage />
            <AttributeList />
          </v-container>

          <!-- Divider for Left Column, can drag -->
          <div
            id="left-divider"
            class="clean-space fill-height border-thin"
            style="width: 0px; cursor: col-resize"
            @mousedown="startResizingLeft"></div>

          <!-- Middle Column -->
          <v-container
            id="middle-column"
            class="clean-space fill-height flex-row-grow-1 flex-column">
            <ElementHierarchy />
            <JsonSelector />
          </v-container>

          <!-- Divider for Right Column, can drag -->
          <div
            id="right-divider"
            class="clean-space fill-height border-thin"
            style="width: 0px; cursor: col-resize"
            @mousedown="startResizingRight"></div>

          <!-- Right Column -->
          <!-- Use :style to implement divider deag feature -->
          <v-container
            id="right-column"
            class="clean-space fill-height flex-column"
            :style="{
              width: settingStore.rightColumnWidth + 'px',
              minWidth: '250px',
              maxWidth: '750px',
              flexShrink: '0',
            }">
            <SettingArea />
            <AttributeEditor />
            <Status />
          </v-container>
        </v-container>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import Alert from "./components/Alert.vue";
import SocketState from "./components/SocketState.vue";

import ButtonArea from "./components/ButtonArea.vue";

import ElementTree from "./components/ElementTree.vue";
import PreviewImage from "./components/PreviewImage.vue";
import AttributeList from "./components/AttributeList.vue";

import ElementHierarchy from "./components/ElementHierarchy.vue";
import JsonSelector from "./components/JsonSelector.vue";

import SettingArea from "./components/SettingArea.vue";
import AttributeEditor from "./components/AttributeEditor.vue";
import Status from "./components/Status.vue";

import { useSettingStore } from "./store";

const settingStore = useSettingStore();

let intStartX = 0;
let intStartWidth = 0;
let boolResizing = false;

function startResizingLeft(event: MouseEvent): void {
  boolResizing = true;
  intStartX = event.clientX;
  intStartWidth = settingStore.leftColumnWidth;

  window.addEventListener("mousemove", mouseMoveHandlerLeft);
  window.addEventListener("mouseup", stopResizing);
}

function mouseMoveHandlerLeft(event: MouseEvent): void {
  if (!boolResizing) return;
  const intDistanceX = event.clientX - intStartX;

  let intNewWidth = intStartWidth + intDistanceX;
  // Ensure the new width is within the allowed range
  intNewWidth = Math.max(250, Math.min(750, intNewWidth));
  // Round the new width to the nearest 50px
  intNewWidth = Math.round(intNewWidth / 50) * 50;

  settingStore.leftColumnWidth = intNewWidth;
}

function startResizingRight(event: MouseEvent): void {
  boolResizing = true;
  intStartX = event.clientX;
  intStartWidth = settingStore.rightColumnWidth;

  window.addEventListener("mousemove", mouseMoveHandlerRight);
  window.addEventListener("mouseup", stopResizing);
}

function mouseMoveHandlerRight(event: MouseEvent): void {
  if (!boolResizing) return;
  const intDistanceX = event.clientX - intStartX;

  let intNewWidth = intStartWidth - intDistanceX;
  intNewWidth = Math.max(250, Math.min(750, intNewWidth));
  intNewWidth = Math.round(intNewWidth / 50) * 50;

  settingStore.rightColumnWidth = intNewWidth;
}

function stopResizing(): void {
  boolResizing = false;
  window.removeEventListener("mousemove", mouseMoveHandlerLeft);
  window.removeEventListener("mouseup", stopResizing);
}
</script>

<style scoped></style>
