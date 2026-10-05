// FileName: lifecycle.ts

import type { Dict_ProjectRun_Detail, RunExecutionContext, RunEndedFact } from "./types";
import { getErrorMessage } from "../../shared/error";
import { loggerMain } from "../Logging/logger";

type Listener_RunEnded = () => void;

const setRunEndedListener = new Set<Listener_RunEnded>();

export function onRunEnded(listener: Listener_RunEnded): () => void {
  setRunEndedListener.add(listener);
  return () => {
    setRunEndedListener.delete(listener);
  };
}

export function notifyRunEnded(): void {
  for (const listener of setRunEndedListener) {
    try {
      listener();
    } catch (e: unknown) {
      loggerMain.error(`Run-ended listener failed: ${getErrorMessage(e)}`);
    }
  }
}

const setRunActivityListener = new Set<() => void>();

export function onRunActivityChanged(listener: () => void): void {
  setRunActivityListener.add(listener);
}

export function notifyRunActivityChanged(): void {
  for (const listener of setRunActivityListener) {
    try {
      listener();
    } catch (e: unknown) {
      loggerMain.error(`Run-activity listener failed: ${getErrorMessage(e)}`);
    }
  }
}

type RunFinishedListener = (
  detail: Dict_ProjectRun_Detail,
  context: RunExecutionContext,
  fact: RunEndedFact,
) => void;
const setRunFinishedListener = new Set<RunFinishedListener>();

export function onRunFinished(listener: RunFinishedListener): void {
  setRunFinishedListener.add(listener);
}

export function notifyRunFinished(
  detail: Dict_ProjectRun_Detail,
  context: RunExecutionContext,
  fact: RunEndedFact,
): void {
  for (const listener of setRunFinishedListener) {
    try {
      listener(detail, context, fact);
    } catch (e: unknown) {
      loggerMain.error(`Run result listener failed: ${getErrorMessage(e)}`);
    }
  }
}
