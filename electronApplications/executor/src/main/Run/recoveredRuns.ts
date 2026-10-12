// FileName: recoveredRuns.ts

import { getErrorMessage } from "../../shared/error";
import { loggerMain } from "../Logging/logger";
import { notifyRunActivityChanged, notifyRunEnded } from "./lifecycle";

interface RecoveredRunObserver {
  runId: string;
  historyId: number;
  processId: number;
  sessionKey: string;
  onProcessExited: () => void;
}

const mapRecoveredRun = new Map<string, RecoveredRunObserver>();
let timerObservation: NodeJS.Timeout | undefined;

export function isRecoveredProcessPresent(processId: number): boolean {
  try {
    process.kill(processId, 0);
    return true;
  } catch (e: unknown) {
    // A process we cannot inspect still counts toward the running limit; only ESRCH confirms it no longer exists.
    return !(e instanceof Error && "code" in e && e.code === "ESRCH");
  }
}

export function hasRecoveredRun(): boolean {
  return mapRecoveredRun.size !== 0;
}

export function isRecoveredRunHistoryActive(historyId: number): boolean {
  return [...mapRecoveredRun.values()].some((observer) => observer.historyId === historyId);
}

export function getRecoveredConsoleRunIds(sessionKey: string | undefined): string[] {
  return [...mapRecoveredRun.values()]
    .filter((observer) => observer.sessionKey === sessionKey)
    .map((observer) => observer.runId);
}

export function getOtherRecoveredRunCount(sessionKey: string | undefined): number {
  return [...mapRecoveredRun.values()].filter(
    (observer) => observer.sessionKey !== sessionKey,
  ).length;
}

function observeRecoveredRuns(): void {
  for (const observer of mapRecoveredRun.values()) {
    if (isRecoveredProcessPresent(observer.processId)) continue;
    try {
      observer.onProcessExited();
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to recover Console Run ${observer.runId}: ${getErrorMessage(e)}`,
      );
    }
    mapRecoveredRun.delete(observer.runId);
    notifyRunActivityChanged();
    notifyRunEnded();
  }
  if (!mapRecoveredRun.size) {
    clearInterval(timerObservation);
    timerObservation = undefined;
  }
}

export function watchRecoveredRun(observer: RecoveredRunObserver): void {
  // Observing a PID does not restore its child-process streams or authorize a new launch.
  mapRecoveredRun.set(observer.runId, observer);
  if (!timerObservation) {
    timerObservation = setInterval(observeRecoveredRuns, 2000);
    timerObservation.unref();
  }
}

export function stopRecoveredRunObservation(): void {
  clearInterval(timerObservation);
  timerObservation = undefined;
}
