// FileName: commonFunc.ts
import LogicFlow from "@logicflow/core";
import { useFlowchartStore, useInformationStore, useSettingStore } from "./store";
import { DictProject } from "./interface";

declare function acquireVsCodeApi(): {
  postMessage(message: any): void;
};

const vscode = acquireVsCodeApi();

let strCache = "";

export function showAlert(message: string): void {
  const informationStore = useInformationStore();
  informationStore.information = message;
  informationStore.showAlert = true;
}

let dictFinal: DictProject = {
  nodes: [],
  edges: [],
  executeMode: "Run",
  logLevel: "DEBUG",
  recordVideo: false,
  stopShortcut: true,
  highlightUi: false,
  customPrjArgs: [],
};

export function initDictFinal(documentData: DictProject): void {
  dictFinal = documentData;
}

export function updateLocalData(
  lfObj: LogicFlow | null,
  executeMode: "Run" | "Debug" | null,
  logLevel: "VERBOSE" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL" | null,
  recordVideo: boolean | null,
  stopShortcut: boolean | null,
  highlightUi: boolean | null,
  customPrjArgs: [string, any][] | null
): void {
  console.log("--updateLocalData--");

  if (lfObj !== null) {
    // Clean the previous data of nodes and edges.
    dictFinal.nodes = [];
    dictFinal.edges = [];

    const nodes = lfObj.graphModel.nodes;
    const edges = lfObj.graphModel.edges;

    nodes.forEach((node) => {
      const dictTemp: {
        pyFile?: string;
        condition?: string;
      } = {};

      const dictProperties = node.properties;
      if (
        "pyFile" in dictProperties &&
        dictProperties.pyFile === "liberrpa.FlowControl.Start.py" &&
        dictProperties.condition
      ) {
        // NOTE: I didn't know why the Start Node will always create the "condition", just remove it now.
        console.log("dictProperties:", dictProperties);
        delete dictProperties.condition;
      }

      if ("pyFile" in dictProperties) {
        dictTemp.pyFile = dictProperties.pyFile;
        // console.log("pyFile:", node.type, dictProperties.pyFile);
      }
      if ("condition" in dictProperties) {
        dictTemp.condition = dictProperties.condition;
        // console.log("condition", node.type, dictProperties.condition);
      }
      dictFinal.nodes.push({
        id: node.id,
        type: node.type,
        x: node.x,
        y: node.y,
        text: node.text.value,
        properties: dictTemp,
      });
    });

    edges.forEach((edge) => {
      dictFinal.edges?.push({
        id: edge.id,
        type: edge.type,
        sourceNodeId: edge.sourceNodeId,
        targetNodeId: edge.targetNodeId,
        text: edge.text.value,
        startPoint: { x: edge.startPoint.x, y: edge.startPoint.y },
        endPoint: { x: edge.endPoint.x, y: edge.endPoint.y },
      });
    });

    // Update flowchartStore.data, otherwise if FlowchartArea will use the original file data.
    const flowchartStore = useFlowchartStore();
    flowchartStore.data = {
      nodes: dictFinal.nodes,
      edges: dictFinal.edges,
    };
  }

  if (executeMode !== null) {
    dictFinal.executeMode = executeMode;
  }

  if (logLevel !== null) {
    dictFinal.logLevel = logLevel;
  }

  if (recordVideo !== null) {
    dictFinal.recordVideo = recordVideo;
  }

  if (stopShortcut !== null) {
    dictFinal.stopShortcut = stopShortcut;
  }

  if (highlightUi !== null) {
    dictFinal.highlightUi = highlightUi;
  }

  if (customPrjArgs !== null) {
    dictFinal.customPrjArgs = customPrjArgs;
  }

  const strDocument = JSON.stringify(dictFinal, null, 2);

  if (strCache === strDocument) {
    console.log("The flowchart data didn't changed, not update.");
    return;
  } else {
    strCache = strDocument;
  }

  console.log(strDocument);

  vscode.postMessage({ command: "update", data: strDocument });
}

export function clickBlockExecute(pyFile: string): void {
  console.log("clickExecute", pyFile);
  const settingStore = useSettingStore();
  vscode.postMessage({
    command: "execute",
    data: { pyFile: pyFile, executeMode: settingStore.executeMode },
  });
}

export function clickStartExecute(): void {
  console.log("clickStartExecute");
  const settingStore = useSettingStore();
  vscode.postMessage({
    command: "executeProject",
    data: { executeMode: settingStore.executeMode },
  });
}

export function clickOpen(pyFile: string): void {
  console.log("clickOpen", pyFile);
  vscode.postMessage({ command: "open", path: pyFile });
}
