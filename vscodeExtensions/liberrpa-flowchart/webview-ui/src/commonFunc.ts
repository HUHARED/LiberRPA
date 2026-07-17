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
import { createTwoFilesPatch } from "diff";

declare function acquireVsCodeApi(): {
  postMessage(message: unknown): void;
};

const vscode = acquireVsCodeApi();

export function notifyWebviewReady(): void {
  vscode.postMessage({ command: "ready" });
}

export function showAlert(message: string): void {
  const informationStore = useInformationStore();
  informationStore.information = message;
  informationStore.showAlert = true;
}

export function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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
  dictFinal = JSON.parse(JSON.stringify(documentData)) as DictProject;
}

function stringifyProject(project: DictProject): string {
  return JSON.stringify(project, null, 2);
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
  const dictBefore = JSON.parse(JSON.stringify(dictFinal)) as DictProject;

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

  const strBefore = stringifyProject(dictBefore);
  const strAfter = stringifyProject(dictFinal);

  if (strBefore === strAfter) {
    console.log("[updateLocalData] No change.");
    return;
  }

  const patchText = createTwoFilesPatch(
    "before.flow",
    "after.flow",
    strBefore,
    strAfter,
    "",
    "",
    {
      context: 3,
    }
  );

  const arrLines = patchText.split(/\r?\n/);

  console.log("[updateLocalData] Diff:");

  for (const line of arrLines) {
    if (line.startsWith("---") || line.startsWith("+++")) {
      console.log(`%c${line}`, "color: #888;");
    } else if (line.startsWith("@@")) {
      console.log(`%c${line}`, "color: #569cd6;");
    } else if (line.startsWith("-")) {
      console.log(`%c${line}`, "color: #f85149; background: rgba(248, 81, 73, 0.12);");
    } else if (line.startsWith("+")) {
      console.log(`%c${line}`, "color: #3fb950; background: rgba(63, 185, 80, 0.12);");
    } else {
      console.log(`%c${line}`, "color: inherit;");
    }
  }

  vscode.postMessage({ command: "update", data: JSON.stringify(dictFinal, null, 2) });
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
