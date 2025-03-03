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

// import { dictTemp } from "../_testData";
const flowchartStore = useFlowchartStore();
const informationStore = useInformationStore();
const settingStore = useSettingStore();

const flowchartContainer = ref<HTMLElement | null>(null);

let selectedNode: LogicFlow.GraphData | null = null;
const TRANSLATION_DISTANCE = 40;
// flowchartStore.data = dictTemp;

let lfObj: LogicFlow;

onMounted(() => {
  const container = flowchartContainer.value;

  if (container instanceof HTMLElement) {
    const resizeObserver = new ResizeObserver(() => {
      /* console.log(
        `width = ${container.offsetWidth}, height = ${container.offsetHeight}`
      ); */

      getLogicFlowObj(container);
      lfObj.render(flowchartStore.data);
      initDragEvent();
    });

    resizeObserver.observe(container);

    onUnmounted(() => {
      resizeObserver.disconnect();
    });
  } else {
    console.error("flowchartContainer is not an HTMLElement:", container);
  }
});

function getLogicFlowObj(container: HTMLElement): void {
  lfObj = new LogicFlow({
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
    // edgeType: "CommonLine",
    edgeGenerator: (sourceNode, _targetNode, _currentEdge) => {
      // console.log(`Link from a "${sourceNode.type}" to a "${targetNode.type}"`);
      const arrEdges = getCurrentSourceEdges(sourceNode, lfObj);
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
      // console.log(`Try to create a new ${strEdgeType} edge.`);
      return strEdgeType;
    },
    keyboard: {
      enabled: true,
      shortcuts: [
        // The default hotkeys in LogicFlow are not overrode: 'cmd + z', 'ctrl + z' to undo, 'cmd + y', 'ctrl + y' to redo.
        {
          keys: ["delete", "backspace"],
          callback: () => {
            const lfGraphData: LogicFlow.GraphData = lfObj.getSelectElements(true);
            console.log(lfGraphData);
            lfObj.clearSelectElements();
            if (lfGraphData.nodes.length >= 1 && lfGraphData.nodes[0].type === "Start") {
              showAlert("Start node cannot be deleted.");
              return;
            }
            lfGraphData.nodes.forEach((node) => {
              lfObj.deleteNode(node.id);
            });
            lfGraphData.edges.forEach((edge) => {
              lfObj.deleteEdge(edge.id);
            });
          },
        },
        {
          keys: ["cmd + c", "ctrl + c"],
          callback: () => {
            const lfGraphData: LogicFlow.GraphData = lfObj.getSelectElements(true);
            if (lfGraphData.edges.length > 0) {
              showAlert("Line cannot be copied.");
              return;
            }
            if (
              lfGraphData.nodes.length >= 1 &&
              (lfGraphData.nodes[0].type === "Start" ||
                lfGraphData.nodes[0].type === "SubStart")
            ) {
              showAlert("Start and SubStart node cannot be copied.");
            }
            selectedNode = lfGraphData;
          },
        },
        {
          keys: ["cmd + v", "ctrl + v"],
          callback: () => {
            if (selectedNode && selectedNode.nodes) {
              lfObj.clearSelectElements();
              const element: LogicFlow.GraphElements = lfObj.addElements(selectedNode);
              if (!element) {
                showAlert("Paste failed.");
                return;
              }
              // Set selection on the copy and move it, to make it more visible.
              element.nodes.forEach((node) => {
                lfObj.selectElementById(node.id);
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

  flowchartStore.lfObj = lfObj;

  lfObj.register(StartNode);
  lfObj.register(SubStartNode);
  lfObj.register(EndNode);
  lfObj.register(BlockNode);
  lfObj.register(ChooseNode);
  lfObj.register(CommonLineEdge);
  lfObj.register(TrueLineEdge);
  lfObj.register(FalseLineEdge);
  lfObj.register(ExceptionLineEdge);

  lfObj.setTheme({
    arrow: {
      offset: 8,
      verticalLength: 3,
    },
  });

  lfObj.on("connection:not-allowed", (data) => {
    if (data.msg) {
      showAlert(data.msg);
    }
  });

  // Update Node Info when click a node.
  lfObj.on("node:click", (data) => {
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
  lfObj.on("blank:click", () => {
    // console.log(data);
    informationStore.nodeId = "";
    informationStore.nodeType = "";
    informationStore.nodeText = "";
    informationStore.nodeProperty = "";
  });

  // Generate json when flowchart modified.
  lfObj.on("history:change", () => {
    updateLocalData(lfObj, null, null, null, null, null, null);
    // console.log("history:change");
  });
}

watch(
  () => flowchartStore.nodePanelMounted,
  (newValue: boolean) => {
    if (newValue === true) {
      initDragEvent();
    }
  }
);

function initDragEvent(): void {
  const elementNodePanel = document.querySelector("#node-panel");
  if (elementNodePanel) {
    elementNodePanel.addEventListener("mousedown", (event) => {
      const element = event.target as SVGElement;
      // console.log(element);
      // Can't get type of text from the element, so use stroke's color to distinguish Node type
      const strStroke = element.getAttribute("stroke");
      // console.log(strStroke);
      let strType: string = "";
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

      if (strType !== "") {
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
            // SubStart.py or End.py, the files are in Python library.
            nodeNew.properties.pyFile = "liberrpa.FlowControl." + strType + ".py";
            break;
        }
        lfObj.dnd.startDrag(nodeNew);
      } else {
        console.error("It is not a node.");
      }
    });
  }
}
</script>

<style scoped></style>
