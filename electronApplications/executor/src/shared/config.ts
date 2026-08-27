// FileName: config.ts

// Persisted values in Executor.jsonc.
export interface Dict_ExecutorConfig {
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
