// FileName: types.ts

import type {
  RunSource,
  RunOutputs,
  RunEmailOutputKeys,
  RunEmailOutputContext,
  RunEndedStatus,
} from "../../shared/run";
export enum RunTerminationReason {
  Cancel = "cancel",
  Shutdown = "shutdown",
  Timeout = "timeout",
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
  status: RunEndedStatus;
  retryEligible: boolean;
  outputs: RunOutputs;
  emailOutputContext: RunEmailOutputContext;
  errorSummary: { type: string; message: string } | null;
}

export interface RunExecutionContext {
  source: RunSource;
  jobId: string;
  attemptNumber: number;
  runId?: string;
  packagePath?: string;
  emailOutputKeys?: RunEmailOutputKeys;
  beforeSpawn?: (hasOtherActiveRun: boolean, startedAt: string) => void;
  onStarted?: (fact: RunStartedFact) => void;
  onStopping?: (reason: RunTerminationReason) => void;
  onEnded?: (fact: RunEndedFact) => void;
}
