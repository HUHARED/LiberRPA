// FileName: lifecycle.ts

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
