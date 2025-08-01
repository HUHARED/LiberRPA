export interface DictBasicConfig {
  outputLogPath: string;
  localServerPort: number;
  uiAnalyzerTheme: "light" | "dark";
  uiAnalyzerMinimizeWindow: boolean;
}

export interface DictInvokeResult {
  success: boolean;
  data?: any;
}

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
  spec: { [key: string]: string };
  children?: DictEleTreeItem[];
}
