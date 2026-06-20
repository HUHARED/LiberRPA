<!-- FileName: NodePanel.vue -->
<template>
  <v-container class="pa-0 ma-0 border-b-thin">
    <v-label class="pa-2 ma-0 text-center" style="display: block">Node Panel</v-label>
    <div
      id="node-panel"
      ref="flowchartContainer"
      class="pa-0 ma-0"
      style="width: 148px; height: 400px; overflow: hidden"></div
  ></v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { LogicFlow } from "@logicflow/core";
import "@logicflow/core/lib/style/index.css";
import { BlockNode, SubStartNode, EndNode, ChooseNode } from "../customNode";
import { useFlowchartStore, useSettingStore } from "../store";
import type { Flowchart } from "../interface";
const settingStore = useSettingStore();

const flowchartStore = useFlowchartStore();

const flowchartContainer = ref<HTMLElement | null>(null);

const dictNodeExample: Flowchart = {
  nodes: [
    {
      id: "0",
      type: "SubStart",
      x: 75,
      y: 50,
      text: "SubStart",
      properties: {
        pyFile: "liberrpa.FlowControl.SubStart.py",
      },
    },
    {
      id: "1",
      type: "Block",
      x: 75,
      y: 135,
      text: "Block",
      properties: {
        // initDragEvent() in FlowchartArea.vue will update the value.
        pyFile: "...",
      },
    },
    {
      id: "2",
      type: "Choose",
      x: 75,
      y: 240,
      text: "Choose",
      properties: {
        // initDragEvent() in FlowchartArea.vue will update the value.
        condition: "...",
      },
    },
    {
      id: "3",
      type: "End",
      x: 75,
      y: 340,
      text: "End",
      properties: {
        pyFile: "liberrpa.FlowControl.End.py",
      },
    },
  ],
  edges: [],
};

onMounted(() => {
  const container = flowchartContainer.value;

  if (container instanceof HTMLElement) {
    const lfObj = new LogicFlow({
      container: container,
      width: container.offsetWidth,
      height: container.offsetHeight,
      isSilentMode: true,
      stopScrollGraph: true,
      stopZoomGraph: true,
      stopMoveGraph: true,
      history: false,
      background: {
        backgroundColor: settingStore.theme === "light" ? null : "rgb(18, 18, 18)",
      },
    });

    lfObj.register(SubStartNode);
    lfObj.register(EndNode);
    lfObj.register(BlockNode);
    lfObj.register(ChooseNode);

    lfObj.render(dictNodeExample);
    flowchartStore.nodePanelMounted = true;
  } else {
    console.error("flowchartContainer is not an HTMLElement:", container);
  }
});

onUnmounted(() => {
  flowchartStore.nodePanelMounted = false;
});
</script>

<style scoped></style>
