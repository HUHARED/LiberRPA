// FileName: interface.ts

export interface UiAnalyzerInitialization {
  localServerPort: number;
  theme: "light" | "dark";
  minimizeWindow: boolean;
  token: string;
}

export type DictInvokeResult =
  | {
      success: true;
      data?: unknown;
    }
  | {
      success: false;
      data: string;
    };

export type MainInvokeCommand =
  | "cmd-minimize-window"
  | "cmd-restore-window"
  | "cmd-toggle-socket-status";

export type RendererLogLevel =
  | "error"
  | "warn"
  | "info"
  | "http"
  | "verbose"
  | "debug"
  | "silly";

export interface SelectorWindow {
  window: { [key: string]: string };
}

export interface SelectorNonWindow extends SelectorWindow {
  category: "uia" | "html" | "image";
  specification: { [key: string]: string }[];
}

export type Selector = SelectorWindow | SelectorNonWindow;

export interface DictForUiAnalyzer {
  selector: Selector;
  attributes: { [key: string]: string };
  preview?: string;
}

export interface DictEleTreeItem {
  id: number;
  title: string;
  attributes: { [key: string]: string };
  children?: DictEleTreeItem[];
}

export type ElementTreeResult = [DictEleTreeItem[], number[], number];

export type UiAnalyzerOperationName =
  | "indicate_uia"
  | "indicate_chrome"
  | "indicate_image"
  | "indicate_window"
  | "validate";

export type UiAnalyzerOperationPhase = "idle" | "running" | "buildingElementTree";

export type UiAnalyzerServerMessage =
  | {
      operationId: number;
      messageType: "operationResult";
      boolSuccess: boolean;
      data: unknown;
    }
  | {
      operationId: number;
      messageType: "elementTreeResult";
      boolSuccess: boolean;
      data: unknown;
    }
  | {
      operationId: number;
      messageType: "operationCompleted";
    };
