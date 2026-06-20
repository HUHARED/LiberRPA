// FileName: interface.ts

/* Basic JSON */

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

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

export interface DictPosition {
  x: number;
  y: number;
}

interface BaseEdge {
  id: string;
  sourceNodeId: string;
  targetNodeId: string;
  startPoint: DictPosition;
  endPoint: DictPosition;
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
  // Nodes cannot be empty in valid .flow files, but TypeScript cannot express that here.
  // Runtime validation is handled in the extension layer.
  nodes: FlowNode[];
  edges: FlowEdge[];
}

/* Project Arguments */

export type ExecuteMode = "Run" | "Debug";
export type LogLevel = "VERBOSE" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

export type CustomPrjArg = [name: string, value: JsonValue];

export interface BuildinProjectArguments {
  logLevel: LogLevel;
  recordVideo: boolean;
  stopShortcut: boolean;
  highlightUi: boolean;
}

/* Combined project types */

export interface DictProject extends Flowchart, BuildinProjectArguments {
  executeMode: ExecuteMode;
  customPrjArgs: CustomPrjArg[];
}

export type Theme = "light" | "dark";

export interface DictProjectForWebview extends DictProject {
  // theme is added by the extension when sending data to the webview.
  theme: Theme;
}
