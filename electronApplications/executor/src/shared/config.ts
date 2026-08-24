// FileName: config.ts

export interface DictBasicConfig {
  outputLogPath: string;
  localServerPort: number;
  uiAnalyzerTheme: "light" | "dark";
  uiAnalyzerMinimizeWindow: boolean;
  componentRepositoryPath: string;
}

// Persisted values in Executor.jsonc.
export interface DictExecutorConfig {
  theme: "light" | "dark";
  keepRdpSession: boolean;
  keepRdpSessionWidth: number;
  keepRdpSessionHeight: number;
  logTimeoutEnable: boolean;
  logTimeoutDays: number;
  videoTimeoutEnable: boolean;
  videoTimeoutDays: number;
  videoSizeEnable: boolean;
  videoSizeGB: number;
  // An empty string uses basic.jsonc's Executor outputLogPath.
  projectLogFolderPath: string;
  timezone: string;
}
