// FileName: types.ts

import type { RunSource, RunOutputs, RunTerminalStatus } from "../../shared/run";
import type { Str_RunConflictPolicy } from "../../shared/schedule";
import type {
  Dict_PythonEnvironmentSelection,
  Dict_RunOptions,
} from "../../shared/runOptions";

export interface ProjectRunDetails
  extends Dict_RunOptions, Dict_PythonEnvironmentSelection {
  run_conflict_policy?: Str_RunConflictPolicy;
  schedule_name: string | null;
  id: number;
  name: string;
  version: string;
}

export enum RunTerminationReason {
  Cancel = "cancel",
  Shutdown = "shutdown",
  Timeout = "timeout",
}

export interface RunExecutionContext {
  source: RunSource;
  jobId: string;
  attempt: number;
  runId?: string;
  consoleUrl?: string;
  packagePath?: string;
  beforeSpawn?: (hasOtherActiveRun: boolean, startedAt: string) => void;
  onStarted?: (fact: RunStartedFact) => void;
  onStopping?: (reason: RunTerminationReason) => void;
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
  status: RunTerminalStatus;
  retryEligible: boolean;
  outputs: RunOutputs;
  errorSummary: { type: string; message: string } | null;
}
