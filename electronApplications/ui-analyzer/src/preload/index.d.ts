// FileName: index.d.ts

import type {
  DictInvokeResult,
  MainInvokeCommand,
  RendererLogLevel,
  UiAnalyzerInitialization,
} from "../shared/interface";

export interface UiAnalyzerApi {
  logToMain(level: RendererLogLevel, message: string): void;
  invokeMain(command: MainInvokeCommand, data?: unknown): Promise<DictInvokeResult>;
  onInitSetting(callback: (data: UiAnalyzerInitialization) => void): () => void;
}

declare global {
  interface Window {
    uiAnalyzer: UiAnalyzerApi;
  }
}
