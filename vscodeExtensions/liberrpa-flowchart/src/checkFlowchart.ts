// FileName: checkFlowchart.ts
import type {
  FlowNode,
  FlowEdge,
  ExecuteMode,
  LogLevel,
  JsonValue,
  CustomPrjArg,
  DictProject,
} from "./interface";

type UnknownRecord = Record<string, unknown>;
type BaseNodeRecord = UnknownRecord & {
  id: string;
  x: number;
  y: number;
  text: string;
};
type BaseEdgeRecord = UnknownRecord & {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  startPoint: { x: number; y: number };
  endPoint: { x: number; y: number };
};
const ARR_PROJECT_KEYS = [
  "nodes",
  "edges",
  "executeMode",
  "logLevel",
  "recordVideo",
  "stopShortcut",
  "highlightUi",
  "customPrjArgs",
] as const;

const ARR_NODE_KEYS = ["id", "type", "x", "y", "text", "properties"] as const;

const ARR_EDGE_KEYS = [
  "id",
  "type",
  "sourceNodeId",
  "targetNodeId",
  "startPoint",
  "endPoint",
  "text",
] as const;

/* Basic helper */

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === "boolean";
}

export function isExecuteMode(value: unknown): value is ExecuteMode {
  return value === "Run" || value === "Debug";
}

function isLogLevel(value: unknown): value is LogLevel {
  return (
    value === "VERBOSE" ||
    value === "DEBUG" ||
    value === "INFO" ||
    value === "WARNING" ||
    value === "ERROR" ||
    value === "CRITICAL"
  );
}

function hasExactKeys(value: UnknownRecord, expectedKeys: readonly string[]): boolean {
  const actualKeys = Object.keys(value);

  return (
    actualKeys.length === expectedKeys.length &&
    actualKeys.every((key) => expectedKeys.includes(key))
  );
}
function isPoint(value: unknown): value is { x: number; y: number } {
  if (!isRecord(value)) {
    return false;
  }

  return hasExactKeys(value, ["x", "y"]) && isNumber(value.x) && isNumber(value.y);
}

/* Check Nodes */

function isBaseNodeRecord(value: unknown): value is BaseNodeRecord {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isString(value.id) && isNumber(value.x) && isNumber(value.y) && isString(value.text)
  );
}

function isStartNode(value: unknown): value is Extract<FlowNode, { type: "Start" }> {
  if (!isBaseNodeRecord(value)) {
    return false;
  }

  if (!hasExactKeys(value, ARR_NODE_KEYS)) {
    return false;
  }

  if (value.id !== "LiberRPA_Start" || value.type !== "Start" || value.text !== "Start") {
    return false;
  }

  if (!isRecord(value.properties)) {
    return false;
  }

  return (
    hasExactKeys(value.properties, ["pyFile"]) &&
    value.properties.pyFile === "liberrpa.FlowControl.Start.py"
  );
}

function isSubStartNode(value: unknown): value is Extract<FlowNode, { type: "SubStart" }> {
  if (!isBaseNodeRecord(value)) {
    return false;
  }

  if (!hasExactKeys(value, ARR_NODE_KEYS)) {
    return false;
  }

  if (value.type !== "SubStart") {
    return false;
  }

  if (!isRecord(value.properties)) {
    return false;
  }

  return (
    hasExactKeys(value.properties, ["pyFile"]) &&
    value.properties.pyFile === "liberrpa.FlowControl.SubStart.py"
  );
}

function isEndNode(value: unknown): value is Extract<FlowNode, { type: "End" }> {
  if (!isBaseNodeRecord(value)) {
    return false;
  }

  if (!hasExactKeys(value, ARR_NODE_KEYS)) {
    return false;
  }

  if (value.type !== "End" || value.text !== "End") {
    return false;
  }

  if (!isRecord(value.properties)) {
    return false;
  }

  return (
    hasExactKeys(value.properties, ["pyFile"]) &&
    value.properties.pyFile === "liberrpa.FlowControl.End.py"
  );
}

function isBlockNode(value: unknown): value is Extract<FlowNode, { type: "Block" }> {
  if (!isBaseNodeRecord(value)) {
    return false;
  }

  if (!hasExactKeys(value, ARR_NODE_KEYS)) {
    return false;
  }

  if (value.type !== "Block") {
    return false;
  }

  if (!isRecord(value.properties)) {
    return false;
  }

  return hasExactKeys(value.properties, ["pyFile"]) && isString(value.properties.pyFile);
}

function isChooseNode(value: unknown): value is Extract<FlowNode, { type: "Choose" }> {
  if (!isBaseNodeRecord(value)) {
    return false;
  }

  if (!hasExactKeys(value, ARR_NODE_KEYS)) {
    return false;
  }

  if (value.type !== "Choose") {
    return false;
  }

  if (!isRecord(value.properties)) {
    return false;
  }

  return (
    hasExactKeys(value.properties, ["condition"]) && isString(value.properties.condition)
  );
}

function isFlowNode(value: unknown): value is FlowNode {
  if (!isRecord(value)) {
    return false;
  }

  switch (value.type) {
    case "Start":
      return isStartNode(value);

    case "SubStart":
      return isSubStartNode(value);

    case "End":
      return isEndNode(value);

    case "Block":
      return isBlockNode(value);

    case "Choose":
      return isChooseNode(value);

    default:
      return false;
  }
}

/* Check Edges */
function isBaseEdgeRecord(value: unknown): value is BaseEdgeRecord {
  if (!isRecord(value)) {
    return false;
  }

  return (
    isString(value.id) &&
    isString(value.sourceNodeId) &&
    isString(value.targetNodeId) &&
    isPoint(value.startPoint) &&
    isPoint(value.endPoint)
  );
}

function isCommonLineEdge(
  value: unknown
): value is Extract<FlowEdge, { type: "CommonLine" }> {
  if (!isBaseEdgeRecord(value)) {
    return false;
  }

  return (
    hasExactKeys(value, ARR_EDGE_KEYS) && value.type === "CommonLine" && value.text === ""
  );
}

function isExceptionLineEdge(
  value: unknown
): value is Extract<FlowEdge, { type: "ExceptionLine" }> {
  if (!isBaseEdgeRecord(value)) {
    return false;
  }

  return (
    hasExactKeys(value, ARR_EDGE_KEYS) &&
    value.type === "ExceptionLine" &&
    value.text === "Exception"
  );
}

function isTrueLineEdge(value: unknown): value is Extract<FlowEdge, { type: "TrueLine" }> {
  if (!isBaseEdgeRecord(value)) {
    return false;
  }

  return (
    hasExactKeys(value, ARR_EDGE_KEYS) && value.type === "TrueLine" && value.text === "True"
  );
}

function isFalseLineEdge(
  value: unknown
): value is Extract<FlowEdge, { type: "FalseLine" }> {
  if (!isBaseEdgeRecord(value)) {
    return false;
  }

  return (
    hasExactKeys(value, ARR_EDGE_KEYS) &&
    value.type === "FalseLine" &&
    value.text === "False"
  );
}

function isFlowEdge(value: unknown): value is FlowEdge {
  if (!isRecord(value)) {
    return false;
  }

  switch (value.type) {
    case "CommonLine":
      return isCommonLineEdge(value);

    case "ExceptionLine":
      return isExceptionLineEdge(value);

    case "TrueLine":
      return isTrueLineEdge(value);

    case "FalseLine":
      return isFalseLineEdge(value);

    default:
      return false;
  }
}

/* Check other values */

function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || isString(value) || isNumber(value) || isBoolean(value)) {
    return true;
  }

  if (Array.isArray(value)) {
    return value.every(isJsonValue);
  }

  if (isRecord(value)) {
    return Object.values(value).every(isJsonValue);
  }

  return false;
}

function isCustomPrjArg(value: unknown): value is CustomPrjArg {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    isString(value[0]) &&
    isJsonValue(value[1])
  );
}

export function isDictProject(value: unknown): value is DictProject {
  if (!isRecord(value)) {
    return false;
  }

  if (!hasExactKeys(value, ARR_PROJECT_KEYS)) {
    return false;
  }

  if (!Array.isArray(value.nodes) || value.nodes.length === 0) {
    return false;
  }

  if (!value.nodes.every(isFlowNode)) {
    return false;
  }

  if (!Array.isArray(value.edges)) {
    return false;
  }

  if (!value.edges.every(isFlowEdge)) {
    return false;
  }

  return (
    isExecuteMode(value.executeMode) &&
    isLogLevel(value.logLevel) &&
    isBoolean(value.recordVideo) &&
    isBoolean(value.stopShortcut) &&
    isBoolean(value.highlightUi) &&
    Array.isArray(value.customPrjArgs) &&
    value.customPrjArgs.every(isCustomPrjArg)
  );
}

export function parseFlowProjectFromText(text: string): DictProject {
  let parsed: unknown;

  try {
    parsed = JSON.parse(text);
  } catch (error) {
    throw new Error("The .flow file is not valid JSON.", { cause: error });
  }

  if (!isDictProject(parsed)) {
    throw new Error("The .flow file structure is invalid.");
  }

  return parsed;
}
