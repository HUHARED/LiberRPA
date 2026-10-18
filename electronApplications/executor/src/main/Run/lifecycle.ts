// FileName: lifecycle.ts

import { getErrorMessage } from "../../shared/error";
import type { RunConfig } from "../../shared/run";
import { loggerMain } from "../Logging/logger";
import type { RunEndedFact, RunExecutionContext } from "./types";

type RunHistoryChangedListener = (historyId: number) => void;

type RunFinishedListener = (
  detail: RunConfig,
  context: RunExecutionContext,
  fact: RunEndedFact,
) => void;

const setRunHistoryChangedListener = new Set<RunHistoryChangedListener>();

const setRunActivityListener = new Set<() => void>();

const setRunFinishedListener = new Set<RunFinishedListener>();

export function onRunHistoryChanged(listener: RunHistoryChangedListener): () => void {
  setRunHistoryChangedListener.add(listener);
  return () => {
    setRunHistoryChangedListener.delete(listener);
  };
}

export function notifyRunHistoryChanged(historyId: number): void {
  for (const listener of setRunHistoryChangedListener) {
    try {
      listener(historyId);
    } catch (e: unknown) {
      loggerMain.error(`Run History listener failed: ${getErrorMessage(e)}`);
    }
  }
}

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

export function onRunFinished(listener: RunFinishedListener): void {
  setRunFinishedListener.add(listener);
}

export function notifyRunFinished(
  detail: RunConfig,
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
