<!-- FileName: FlowchartArea.vue -->
<template>
  <v-container class="pa-0 ma-0">
    <div
      ref="flowchartContainer"
      class="pa-0 ma-0"
      style="width: 100%; height: 100vh; overflow: hidden"></div>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import { LogicFlow } from "@logicflow/core";
import "@logicflow/core/lib/style/index.css";
import { useFlowchartStore, useInformationStore, useSettingStore } from "../store";
import { StartNode, BlockNode, SubStartNode, EndNode, ChooseNode } from "../customNode";
import {
  CommonLineEdge,
  TrueLineEdge,
  FalseLineEdge,
  ExceptionLineEdge,
} from "../customEdge";
import { getCurrentSourceEdges } from "../edgeFunc";
import { showAlert, updateLocalData, isObjectRecord } from "../commonFunc";
import { applyLogicFlowTheme } from "../flowchartTheme";

const flowchartStore = useFlowchartStore();
const informationStore = useInformationStore();
const settingStore = useSettingStore();

const flowchartContainer = ref<HTMLElement | null>(null);

let selectedNode: LogicFlow.GraphData | null = null;
const TRANSLATION_DISTANCE = 40;

let lfObj: LogicFlow | null = null; // Current LogicFlow instance for this component.

let resizeObserver: ResizeObserver | null = null;

watch(
  () => settingStore.theme,
  (theme) => {
    if (lfObj) {
      applyLogicFlowTheme(lfObj, theme);
    }
  },
);

onMounted(() => {
  const container = flowchartContainer.value;

  if (!(container instanceof HTMLElement)) {
    console.error("flowchartContainer is not an HTMLElement:", container);
    return;
  }

  const logicFlow = createLogicFlowObj(container);
  lfObj = logicFlow;
  flowchartStore.lfObj = logicFlow;

  logicFlow.render(flowchartStore.data);

  resizeObserver = new ResizeObserver(() => {
    logicFlow.resize(container.offsetWidth, container.offsetHeight);
  });

  resizeObserver.observe(container);
});

onUnmounted(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;

  lfObj = null;
  flowchartStore.lfObj = null;
});

function createLogicFlowObj(container: HTMLElement): LogicFlow {
  const logicFlow = new LogicFlow({
    container: container,
    width: container.offsetWidth,
    height: container.offsetHeight,
    grid: {
      size: 10,
      visible: true,
      type: "dot",
      config: {
        color: "#ababab",
        thickness: 1,
      },
    },
    snapGrid: true,
    adjustEdge: false,
    adjustEdgeStartAndEnd: false,

    edgeGenerator: (sourceNode, _targetNode, _currentEdge) => {
      const currentLfObj = lfObj;

      if (!currentLfObj) {
        // If the instance has not initialized completely.
        return "CommonLine";
      }

      const arrEdges = getCurrentSourceEdges(sourceNode, currentLfObj);
      let strEdgeType: string;

      if (sourceNode.type === "Block") {
        if (arrEdges.length === 0) {
          strEdgeType = "CommonLine";
        } else if (arrEdges[0].type === "CommonLine") {
          strEdgeType = "ExceptionLine";
        } else {
          strEdgeType = "CommonLine";
        }
      } else if (sourceNode.type === "Choose") {
        if (arrEdges.length === 0) {
          strEdgeType = "TrueLine";
        } else if (arrEdges[0].type === "TrueLine") {
          strEdgeType = "FalseLine";
        } else {
          strEdgeType = "TrueLine";
        }
      } else {
        strEdgeType = "CommonLine";
      }
      return strEdgeType;
    },
    keyboard: {
      enabled: true,
      shortcuts: [
        // The default hotkeys in LogicFlow are not overrode: 'cmd + z', 'ctrl + z' to undo, 'cmd + y', 'ctrl + y' to redo.
        {
          keys: ["delete", "backspace"],
          callback: () => {
            const currentLfObj = lfObj;

            if (!currentLfObj) {
              return;
            }

            const lfGraphData: LogicFlow.GraphData = currentLfObj.getSelectElements(true);
            // console.log(lfGraphData);

            currentLfObj.clearSelectElements();

            if (lfGraphData.nodes.some((node) => node.type === "Start")) {
              showAlert("Start node cannot be deleted.");
              return;
            }

            lfGraphData.nodes.forEach((node) => {
              currentLfObj.deleteNode(node.id);
            });
            lfGraphData.edges.forEach((edge) => {
              currentLfObj.deleteEdge(edge.id);
            });
          },
        },
        {
          keys: ["cmd + c", "ctrl + c"],
          callback: () => {
            const currentLfObj = lfObj;

            if (!currentLfObj) {
              return;
            }

            const lfGraphData: LogicFlow.GraphData = currentLfObj.getSelectElements(true);
            if (lfGraphData.edges.length > 0) {
              showAlert("Line cannot be copied.");
              return;
            }

            if (
              lfGraphData.nodes.some(
                (node) => node.type === "Start" || node.type === "SubStart",
              )
            ) {
              showAlert("Start and SubStart node cannot be copied.");
              return;
            }
            selectedNode = lfGraphData;
          },
        },
        {
          keys: ["cmd + v", "ctrl + v"],
          callback: () => {
            const currentLfObj = lfObj;

            if (!currentLfObj) {
              return;
            }

            if (selectedNode && selectedNode.nodes) {
              currentLfObj.clearSelectElements();
              const element: LogicFlow.GraphElements =
                currentLfObj.addElements(selectedNode);

              if (!element) {
                showAlert("Paste failed.");
                return;
              }

              // Set selection on the copy and move it, to make it more visible.
              element.nodes.forEach((node) => {
                currentLfObj.selectElementById(node.id);
                node.x += TRANSLATION_DISTANCE;
                node.y += TRANSLATION_DISTANCE;
                if (node.text) {
                  node.text.x += TRANSLATION_DISTANCE;
                  node.text.y += TRANSLATION_DISTANCE;
                }
              });
            }
          },
        },
      ],
    },
  });

  logicFlow.register(StartNode);
  logicFlow.register(SubStartNode);
  logicFlow.register(EndNode);
  logicFlow.register(BlockNode);
  logicFlow.register(ChooseNode);
  logicFlow.register(CommonLineEdge);
  logicFlow.register(TrueLineEdge);
  logicFlow.register(FalseLineEdge);
  logicFlow.register(ExceptionLineEdge);

  applyLogicFlowTheme(logicFlow, settingStore.theme);

  logicFlow.on("connection:not-allowed", (data) => {
    if (data.msg) {
      showAlert(data.msg);
    }
  });

  // Update Node Info when click a node.
  logicFlow.on("node:click", (data: unknown) => {
    const nodeData = getLogicFlowNodeClickData(data);

    if (!nodeData) {
      console.error("Invalid node:click data:", data);
      return;
    }

    informationStore.nodeId = nodeData.id;
    informationStore.nodeType = nodeData.type;
    informationStore.nodeText = nodeData.text?.value ?? "";

    const pyFile = getStringProperty(nodeData.properties, "pyFile");
    const condition = getStringProperty(nodeData.properties, "condition");
    informationStore.nodeProperty = pyFile || condition;
  });

  // Clean Node Info when click blank area.
  logicFlow.on("blank:click", () => {
    informationStore.nodeId = "";
    informationStore.nodeType = "";
    informationStore.nodeText = "";
    informationStore.nodeProperty = "";
  });

  // Generate json when flowchart modified.
  logicFlow.on("history:change", () => {
    updateLocalData(logicFlow, null, null, null, null, null, null);
    // console.log("history:change");
  });

  return logicFlow;
}

type LogicFlowNodeClickData = {
  id: string;
  type: string;
  text?: {
    value: string;
  };
  properties?: Record<string, unknown>;
};

function getStringProperty(
  properties: Record<string, unknown> | undefined,
  key: string,
): string {
  const value = properties?.[key];

  if (typeof value === "string") {
    return value;
  }

  return "";
}

function getLogicFlowNodeClickData(value: unknown): LogicFlowNodeClickData | null {
  if (!isObjectRecord(value)) {
    return null;
  }

  const data = value.data;

  if (!isObjectRecord(data)) {
    return null;
  }

  if (typeof data.id !== "string" || typeof data.type !== "string") {
    return null;
  }

  const result: LogicFlowNodeClickData = {
    id: data.id,
    type: data.type,
  };

  if (isObjectRecord(data.text) && typeof data.text.value === "string") {
    result.text = {
      value: data.text.value,
    };
  }

  if (isObjectRecord(data.properties)) {
    result.properties = data.properties;
  }

  return result;
}
</script>

<style scoped></style>
