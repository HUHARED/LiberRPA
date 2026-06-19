// FileName: interface.ts

export interface DictPosition {
  x: number;
  y: number;
}

export interface DictNode {
  id: string;
  type: string;
  x: number;
  y: number;
  text: string;
  properties: {
    pyFile?: string;
    condition?: string;
  };
}

export interface DictEdge {
  id: string;
  type: string;
  sourceNodeId: string;
  targetNodeId: string;
  text?: string;
  startPoint?: DictPosition;
  endPoint?: DictPosition;
}

export interface DictFlowchart {
  nodes: DictNode[];
  edges?: DictEdge[];
}

export interface DictBuildinProjectArguments {
  logLevel: "VERBOSE" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  recordVideo: boolean;
  stopShortcut: boolean;
  highlightUi: boolean;
}

export type ExecuteMode = "Run" | "Debug";
export type Theme = "light" | "dark";

export interface DictProject extends DictFlowchart, DictBuildinProjectArguments {
  executeMode: ExecuteMode;
  customPrjArgs: [string, unknown][];
  theme?: Theme;
}
