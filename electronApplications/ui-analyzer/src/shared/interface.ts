// FileName: interface.ts

export interface DictBasicConfig {
  outputLogPath: string;
  localServerPort: number;
  uiAnalyzerTheme: "light" | "dark";
  uiAnalyzerMinimizeWindow: boolean;
  componentRepositoryPath: string;
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

export type MainInvokeCommand = "cmd-toggle-window" | "cmd-toggle-socket-status";
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

export interface DictForUiAnalyzer {
  selector: SelectorWindow | SelectorNonWindow;
  attributes: { [key: string]: string };
  preview: string;
}

export interface DictEleTreeItem {
  id: number;
  title: string;
  attributes: { [key: string]: string };
  children?: DictEleTreeItem[];
}
