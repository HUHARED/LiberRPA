// FileName: commonFunc.ts
import type LogicFlow from "@logicflow/core";
import { useFlowchartStore, useInformationStore, useSettingStore } from "./store";
import type {
  CustomPrjArg,
  DictProject,
  ExecuteMode,
  FlowEdge,
  FlowNode,
  LogLevel,
} from "./interface";

declare function acquireVsCodeApi(): {
  postMessage(message: unknown): void;
};

const vscode = acquireVsCodeApi();

let strCache = "";

export function notifyWebviewReady(): void {
  vscode.postMessage({ command: "ready" });
}

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
  executeMode: ExecuteMode | null,
  logLevel: LogLevel | null,
  recordVideo: boolean | null,
  stopShortcut: boolean | null,
  highlightUi: boolean | null,
  customPrjArgs: CustomPrjArg[] | null
): void {
  console.log("--updateLocalData--");

  if (lfObj !== null) {
    const nodes = lfObj.graphModel.nodes;
    const edges = lfObj.graphModel.edges;

    dictFinal.nodes = nodes.map((node) =>
      buildFlowNodeFromLogicFlowNode(node as LogicFlowNodeLike)
    );

    dictFinal.edges = edges.map((edge) =>
      buildFlowEdgeFromLogicFlowEdge(edge as LogicFlowEdgeLike)
    );

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

type LogicFlowNodeLike = {
  id: string;
  type: string;
  x: number;
  y: number;
  text: {
    value: string;
  };
  properties: Record<string, unknown>;
};

type LogicFlowEdgeLike = {
  id: string;
  type: string;
  sourceNodeId: string;
  targetNodeId: string;
  startPoint: {
    x: number;
    y: number;
  };
  endPoint: {
    x: number;
    y: number;
  };
};

function getStringProperty(properties: Record<string, unknown>, key: string): string {
  const value = properties[key];

  if (typeof value === "string") {
    return value;
  }

  return "";
}

function buildFlowNodeFromLogicFlowNode(node: LogicFlowNodeLike): FlowNode {
  switch (node.type) {
    case "Start":
      return {
        id: "LiberRPA_Start",
        type: "Start",
        x: node.x,
        y: node.y,
        text: "Start",
        properties: {
          pyFile: "liberrpa.FlowControl.Start.py",
        },
      };

    case "SubStart":
      return {
        id: node.id,
        type: "SubStart",
        x: node.x,
        y: node.y,
        text: node.text.value,
        properties: {
          pyFile: "liberrpa.FlowControl.SubStart.py",
        },
      };

    case "End":
      return {
        id: node.id,
        type: "End",
        x: node.x,
        y: node.y,
        text: "End",
        properties: {
          pyFile: "liberrpa.FlowControl.End.py",
        },
      };

    case "Block":
      return {
        id: node.id,
        type: "Block",
        x: node.x,
        y: node.y,
        text: node.text.value,
        properties: {
          pyFile: getStringProperty(node.properties, "pyFile"),
        },
      };

    case "Choose":
      return {
        id: node.id,
        type: "Choose",
        x: node.x,
        y: node.y,
        text: node.text.value,
        properties: {
          condition: getStringProperty(node.properties, "condition"),
        },
      };

    default:
      throw new Error(`Unsupported node type: ${node.type}`);
  }
}

function buildFlowEdgeFromLogicFlowEdge(edge: LogicFlowEdgeLike): FlowEdge {
  const base = {
    id: edge.id,
    sourceNodeId: edge.sourceNodeId,
    targetNodeId: edge.targetNodeId,
    startPoint: {
      x: edge.startPoint.x,
      y: edge.startPoint.y,
    },
    endPoint: {
      x: edge.endPoint.x,
      y: edge.endPoint.y,
    },
  };

  switch (edge.type) {
    case "CommonLine":
      return {
        ...base,
        type: "CommonLine",
        text: "",
      };

    case "ExceptionLine":
      return {
        ...base,
        type: "ExceptionLine",
        text: "Exception",
      };

    case "TrueLine":
      return {
        ...base,
        type: "TrueLine",
        text: "True",
      };

    case "FalseLine":
      return {
        ...base,
        type: "FalseLine",
        text: "False",
      };

    default:
      throw new Error(`Unsupported edge type: ${edge.type}`);
  }
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
