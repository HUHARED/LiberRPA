// FileName: index.d.ts
import type {
  DictBasicConfig,
  DictInvokeResult,
  MainInvokeCommand,
  RendererLogLevel,
} from "../shared/interface";

export interface UiAnalyzerApi {
  logToMain(level: RendererLogLevel, message: string): void;
  invokeMain(command: MainInvokeCommand, data?: unknown): Promise<DictInvokeResult>;
  onInitSetting(callback: (data: [DictBasicConfig, string]) => void): () => void;
}

declare global {
  interface Window {
    uiAnalyzer: UiAnalyzerApi;
  }
}
