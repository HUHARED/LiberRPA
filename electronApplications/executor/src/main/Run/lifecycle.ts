// FileName: lifecycle.ts

import { getErrorMessage } from "../../shared/error";
import type { RunConfig } from "../../shared/run";
import { loggerMain } from "../Logging/logger";
import type { RunEndedFact, RunExecutionContext } from "./types";

type RunEndedListener = () => void;

type RunFinishedListener = (
  detail: RunConfig,
  context: RunExecutionContext,
  fact: RunEndedFact,
) => void;

const setRunEndedListener = new Set<RunEndedListener>();

const setRunActivityListener = new Set<() => void>();

const setRunFinishedListener = new Set<RunFinishedListener>();

export function onRunEnded(listener: RunEndedListener): () => void {
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
