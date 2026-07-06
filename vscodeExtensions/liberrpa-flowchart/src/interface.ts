// FileName: interface.ts

/* Nodes */

interface BaseNode {
  id: string;
  x: number;
  y: number;
  text: string;
}

export interface StartNode extends BaseNode {
  id: "LiberRPA_Start";
  type: "Start";
  text: "Start";
  properties: {
    pyFile: "liberrpa.FlowControl.Start.py";
  };
}

export interface SubStartNode extends BaseNode {
  type: "SubStart";
  properties: {
    pyFile: "liberrpa.FlowControl.SubStart.py";
  };
}

export interface EndNode extends BaseNode {
  type: "End";
  text: "End";
  properties: {
    pyFile: "liberrpa.FlowControl.End.py";
  };
}

export interface BlockNode extends BaseNode {
  type: "Block";
  properties: {
    pyFile: string;
  };
}

export interface ChooseNode extends BaseNode {
  type: "Choose";
  properties: {
    condition: string;
  };
}

export type FlowNode = StartNode | SubStartNode | BlockNode | ChooseNode | EndNode;

/* Edges */

interface BaseEdge {
  id: string;
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
}

export interface CommonLineEdge extends BaseEdge {
  type: "CommonLine";
  text: "";
}

export interface ExceptionLineEdge extends BaseEdge {
  type: "ExceptionLine";
  text: "Exception";
}

export interface TrueLineEdge extends BaseEdge {
  type: "TrueLine";
  text: "True";
}

export interface FalseLineEdge extends BaseEdge {
  type: "FalseLine";
  text: "False";
}

export type FlowEdge = CommonLineEdge | ExceptionLineEdge | TrueLineEdge | FalseLineEdge;

/* Flowchart */

export interface Flowchart {
  // nodes cannot be empty, but edges can.
  nodes: FlowNode[];
  edges: FlowEdge[];
}

/* Project Arguments */

export type ExecuteMode = "Run" | "Debug";
export type LogLevel = "VERBOSE" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type CustomPrjArg = [name: string, value: JsonValue];

interface BuiltInProjectArguments {
  logLevel: LogLevel;
  recordVideo: boolean;
  stopShortcut: boolean;
  highlightUi: boolean;
}

/* Combine them. */

export interface DictProject extends Flowchart, BuiltInProjectArguments {
  executeMode: ExecuteMode;
  customPrjArgs: CustomPrjArg[];
}

type Theme = "light" | "dark";
export interface DictProjectForWebview extends DictProject {
  // theme is added when send data to webview.
  theme: Theme;
}

/* Other */

export type WebviewToExtensionMessage =
  | { command: "ready" }
  | { command: "update"; data: string }
  | { command: "open"; path: string }
  | { command: "execute"; data: { pyFile: string; executeMode: ExecuteMode } }
  | { command: "executeProject"; data: { executeMode: ExecuteMode } };
