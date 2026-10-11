// FileName: config.ts

// Persisted values in Executor.jsonc.
export interface ExecutorConfig {
  theme: "light" | "dark";
  keepRdpSession: boolean;
  keepRdpSessionWidth: number;
  keepRdpSessionHeight: number;
  logRetentionEnabled: boolean;
  logRetentionDays: number;
  videoRetentionEnabled: boolean;
  videoRetentionDays: number;
  videoStorageLimitEnabled: boolean;
  videoStorageLimitGiB: number;
  // An empty string uses basic.jsonc's Executor outputLogPath.
  projectLogFolderPath: string;
  timezone: string;
}
