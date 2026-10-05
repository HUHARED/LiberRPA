// FileName: types.ts

import type { RunSource, RunOutputs, Str_RunHistoryTerminalStatus } from "../../shared/run";
import type { Str_RunConflictPolicy } from "../../shared/schedule";
import type {
  Dict_PythonEnvironmentSelection,
  Dict_RunOptions,
} from "../../shared/runOptions";

export interface Dict_ProjectRun_Detail
  extends Dict_RunOptions, Dict_PythonEnvironmentSelection {
  run_conflict_policy?: Str_RunConflictPolicy;
  schedule_name: string | null;
  id: number;
  name: string;
  version: string;
}

export interface RunExecutionContext {
  source: RunSource;
  jobId: string;
  attempt: number;
  runId?: string;
  packagePath?: string;
  beforeSpawn?: () => void;
  onStarted?: (fact: RunStartedFact) => void;
  onStopping?: (reason: "cancel" | "shutdown" | "timeout") => void;
  onEnded?: (fact: RunEndedFact) => void;
}

export interface RunStartedFact {
  runId: string;
  historyId: number;
  startedAt: string;
  logPath: string;
  processId?: number;
}

export interface RunEndedFact extends RunStartedFact {
  endedAt: string;
  status: Str_RunHistoryTerminalStatus;
  retryEligible: boolean;
  outputs: RunOutputs;
  errorSummary: { type: string; message: string } | null;
}
