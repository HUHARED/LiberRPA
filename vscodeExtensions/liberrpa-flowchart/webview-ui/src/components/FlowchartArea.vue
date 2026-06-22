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
import { ref, watch, onMounted, onUnmounted } from "vue";
import { LogicFlow } from "@logicflow/core";
import "@logicflow/core/lib/style/index.css";
import { useFlowchartStore, useInformationStore, useSettingStore } from "../store";
import { v4 as uuidV4 } from "uuid";
import { StartNode, BlockNode, SubStartNode, EndNode, ChooseNode } from "../customNode";
import {
  CommonLineEdge,
  TrueLineEdge,
  FalseLineEdge,
  ExceptionLineEdge,
} from "../customEdge";
import { getCurrentSourceEdges } from "../edgeFunc";
import { showAlert, updateLocalData } from "../commonFunc";

const flowchartStore = useFlowchartStore();
const informationStore = useInformationStore();
const settingStore = useSettingStore();

const flowchartContainer = ref<HTMLElement | null>(null);

let selectedNode: LogicFlow.GraphData | null = null;
const TRANSLATION_DISTANCE = 40;

let lfObj: LogicFlow | null = null; // Current LogicFlow instance for this component.

let resizeObserver: ResizeObserver | null = null;
let nodePanelElement: Element | null = null;

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

  initDragEvent();

  resizeObserver = new ResizeObserver(() => {
    logicFlow.resize(container.offsetWidth, container.offsetHeight);
  });

  resizeObserver.observe(container);
});

onUnmounted(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;

  removeDragEvent();

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
    background: {
      backgroundColor: settingStore.theme === "light" ? null : "rgb(18, 18, 18)",
    },
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
                (node) => node.type === "Start" || node.type === "SubStart"
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

  logicFlow.setTheme({
    arrow: {
      offset: 8,
      verticalLength: 3,
    },
  });

  logicFlow.on("connection:not-allowed", (data) => {
    if (data.msg) {
      showAlert(data.msg);
    }
  });

  // Update Node Info when click a node.
  logicFlow.on("node:click", (data) => {
    // console.log(data);
    informationStore.nodeId = data.data.id;
    informationStore.nodeType = data.data.type;
    if (data.data.text) {
      informationStore.nodeText = data.data.text.value;
    }
    if (data.data.properties && data.data.properties.pyFile) {
      informationStore.nodeProperty = data.data.properties.pyFile;
    }
    if (data.data.properties && data.data.properties.condition) {
      informationStore.nodeProperty = data.data.properties.condition;
    }
  });

  // Clean Node Info when click blank area.
  logicFlow.on("blank:click", () => {
    // console.log(data);
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

watch(
  () => flowchartStore.nodePanelMounted,
  (newValue: boolean) => {
    if (newValue === true) {
      initDragEvent();
    }
  }
);

function removeDragEvent(): void {
  if (!nodePanelElement) {
    return;
  }

  nodePanelElement.removeEventListener("mousedown", handleNodePanelMouseDown);
  nodePanelElement = null;
}

function initDragEvent(): void {
  const elementTemp = document.querySelector("#node-panel");
  if (!elementTemp) {
    // If the area doesn't be created correctly.
    return;
  }

  if (nodePanelElement === elementTemp) {
    // It has been initialized.
    return;
  }

  removeDragEvent();

  elementTemp.addEventListener("mousedown", handleNodePanelMouseDown);
  nodePanelElement = elementTemp;
}

function handleNodePanelMouseDown(event: Event): void {
  const currentLfObj = lfObj;

  if (!currentLfObj) {
    return;
  }

  if (!(event.target instanceof SVGElement)) {
    return;
  }

  const elementTemp = event.target;

  // Can't get type of text from the element, so use stroke's color to distinguish Node type.
  const strStroke = elementTemp.getAttribute("stroke");

  let strType = "";

  switch (strStroke) {
    case "Teal":
      strType = "SubStart";
      break;

    case "gray":
      strType = "Block";
      break;

    case "orange":
      strType = "Choose";
      break;

    case "Olive":
      strType = "End";
      break;

    default:
      break;
  }

  if (strType === "") {
    console.error(
      "You didn't drop the node into main flowchart area, or it is not a node."
    );
    return;
  }

  const nodeNew: {
    id: string;
    type: string;
    text?: string;
    properties: {
      pyFile?: string;
      condition?: string;
    };
  } = {
    id: uuidV4(),
    type: strType,
    text: strType,
    properties: {},
  };

  switch (strType) {
    case "Block":
      nodeNew.properties.pyFile = ".py";
      break;

    case "Choose":
      nodeNew.properties.condition = `CustomArgs[""]`;
      break;

    default:
      nodeNew.properties.pyFile = `liberrpa.FlowControl.${strType}.py`;
      break;
  }

  currentLfObj.dnd.startDrag(nodeNew);
}
</script>

<style scoped></style>
