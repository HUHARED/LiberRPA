<!-- FileName: NodePanel.vue -->
<template>
  <v-container class="pa-0 ma-0 border-b-thin">
    <v-label class="pa-2 ma-0 text-center" style="display: block">Node Panel</v-label>
    <div class="node-panel-wrapper" style="width: 148px; height: 400px">
      <div
        id="node-panel"
        ref="flowchartContainer"
        class="pa-0 ma-0 node-panel-preview"
        style="width: 148px; height: 400px; overflow: hidden"></div>

      <svg class="node-panel-drag-layer" width="148" height="400" viewBox="0 0 148 400">
        <template v-for="item in arrNodeDragItems" :key="item.type">
          <ellipse
            v-if="item.type === 'SubStart' || item.type === 'End'"
            class="node-panel-drag-shape"
            :cx="item.x"
            :cy="item.y"
            :rx="item.width / 2"
            :ry="item.height / 2"
            @mousedown.prevent.stop="startNodeDrag(item.type)" />

          <rect
            v-else-if="item.type === 'Block'"
            class="node-panel-drag-shape"
            :x="item.x - item.width / 2"
            :y="item.y - item.height / 2"
            :width="item.width"
            :height="item.height"
            :rx="item.radius"
            :ry="item.radius"
            @mousedown.prevent.stop="startNodeDrag(item.type)" />

          <polygon
            v-else-if="item.type === 'Choose'"
            class="node-panel-drag-shape"
            :points="item.diamondPoints"
            @mousedown.prevent.stop="startNodeDrag(item.type)" />
        </template>
      </svg>
    </div>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import { LogicFlow } from "@logicflow/core";
import "@logicflow/core/lib/style/index.css";
import { v4 as uuidV4 } from "uuid";
import {
  BlockNode,
  SubStartNode,
  EndNode,
  ChooseNode,
  NODE_SHAPE_SIZE,
} from "../customNode";
import { useFlowchartStore, useSettingStore } from "../store";
import type { Flowchart, FlowNode } from "../interface";
import { applyLogicFlowTheme } from "../flowchartTheme";

const settingStore = useSettingStore();
const flowchartStore = useFlowchartStore();

const flowchartContainer = ref<HTMLElement | null>(null);
let lfObj: LogicFlow | null = null;

watch(
  () => settingStore.theme,
  (theme) => {
    if (lfObj) {
      applyLogicFlowTheme(lfObj, theme);
    }
  },
);

/* Define nodes' positions and text. */
const ARR_PANEL_NODE_ITEMS = [
  {
    id: "0",
    type: "SubStart",
    x: 75,
    y: 50,
    text: "SubStart",
  },
  {
    id: "1",
    type: "Block",
    x: 75,
    y: 135,
    text: "Block",
  },
  {
    id: "2",
    type: "Choose",
    x: 75,
    y: 240,
    text: "Choose",
  },
  {
    id: "3",
    type: "End",
    x: 75,
    y: 340,
    text: "End",
  },
] satisfies PanelNodeItem[];

function buildPanelPreviewNode(item: PanelNodeItem): FlowNode {
  switch (item.type) {
    case "SubStart":
      return {
        id: item.id,
        type: "SubStart",
        x: item.x,
        y: item.y,
        text: item.text,
        properties: {
          pyFile: "liberrpa.FlowControl.SubStart.py",
        },
      };

    case "Block":
      return {
        id: item.id,
        type: "Block",
        x: item.x,
        y: item.y,
        text: item.text,
        properties: {
          // The value will be updated by buildDragNode().
          pyFile: "...",
        },
      };

    case "Choose":
      return {
        id: item.id,
        type: "Choose",
        x: item.x,
        y: item.y,
        text: item.text,
        properties: {
          // The value will be updated by buildDragNode().
          condition: "...",
        },
      };

    case "End":
      return {
        id: item.id,
        type: "End",
        x: item.x,
        y: item.y,
        text: "End",
        properties: {
          pyFile: "liberrpa.FlowControl.End.py",
        },
      };
  }
}

onMounted(() => {
  const container = flowchartContainer.value;

  if (container instanceof HTMLElement) {
    const logicFlow = new LogicFlow({
      container: container,
      width: container.offsetWidth,
      height: container.offsetHeight,
      isSilentMode: true,
      stopScrollGraph: true,
      stopZoomGraph: true,
      stopMoveGraph: true,
      history: false,
    });
    lfObj = logicFlow;

    logicFlow.register(SubStartNode);
    logicFlow.register(EndNode);
    logicFlow.register(BlockNode);
    logicFlow.register(ChooseNode);
    applyLogicFlowTheme(logicFlow, settingStore.theme);

    const dictNodeExample: Flowchart = {
      nodes: ARR_PANEL_NODE_ITEMS.map(buildPanelPreviewNode),
      edges: [],
    };

    logicFlow.render(dictNodeExample);
  } else {
    console.error("flowchartContainer is not an HTMLElement:", container);
  }
});

onUnmounted(() => {
  lfObj = null;
});

/* Define the drag logic. */

type PanelNodeType = "SubStart" | "Block" | "Choose" | "End";
interface PanelNodeItem {
  id: string;
  type: PanelNodeType;
  x: number;
  y: number;
  text: string;
}
interface PanelNodeDragItem extends PanelNodeItem {
  width: number;
  height: number;
  radius: number;
  diamondPoints: string;
}

function getDiamondPoints(x: number, y: number, width: number, height: number): string {
  const halfWidth = width / 2;
  const halfHeight = height / 2;

  return [
    `${x},${y - halfHeight}`,
    `${x + halfWidth},${y}`,
    `${x},${y + halfHeight}`,
    `${x - halfWidth},${y}`,
  ].join(" ");
}

const arrNodeDragItems: PanelNodeDragItem[] = ARR_PANEL_NODE_ITEMS.map((item) => {
  const size = NODE_SHAPE_SIZE[item.type];

  return {
    ...item,
    width: size.width,
    height: size.height,
    radius: item.type === "Block" ? NODE_SHAPE_SIZE.Block.radius : 0,
    diamondPoints:
      item.type === "Choose"
        ? getDiamondPoints(item.x, item.y, size.width, size.height)
        : "",
  };
});

function buildDragNode(type: PanelNodeType): {
  id: string;
  type: PanelNodeType;
  text: string;
  properties: {
    pyFile?: string;
    condition?: string;
  };
} {
  const nodeNew: {
    id: string;
    type: PanelNodeType;
    text: string;
    properties: {
      pyFile?: string;
      condition?: string;
    };
  } = {
    id: uuidV4(),
    type: type,
    text: type,
    properties: {},
  };

  switch (type) {
    case "Block":
      nodeNew.properties.pyFile = ".py";
      break;

    case "Choose":
      nodeNew.properties.condition = `CustomArgs[""]`;
      break;

    case "SubStart":
      nodeNew.properties.pyFile = "liberrpa.FlowControl.SubStart.py";
      break;

    case "End":
      nodeNew.properties.pyFile = "liberrpa.FlowControl.End.py";
      break;

    default:
      break;
  }

  return nodeNew;
}

function startNodeDrag(type: PanelNodeType): void {
  if (!flowchartStore.lfObj) {
    console.error("Main LogicFlow instance is not initialized.");
    return;
  }

  flowchartStore.lfObj.dnd.startDrag(buildDragNode(type));
}
</script>

<style scoped>
/* Ensure the mouse event works on drag areas rather the their parents layer. */
.node-panel-wrapper {
  position: relative;
  overflow: hidden;
}

.node-panel-preview {
  pointer-events: none;
}

.node-panel-drag-layer {
  position: absolute;
  inset: 0;
}

.node-panel-drag-shape {
  fill: transparent;
  /* Ensure svg elements can respond mouse events */
  pointer-events: all;
  cursor: grab;

  /* See the areas */
  /* fill: rgba(255, 0, 0, 0.12);
  stroke: red;
  stroke-dasharray: 4 4; */
}

.node-panel-drag-shape:active {
  cursor: grabbing;
}
</style>
