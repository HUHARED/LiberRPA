// FileName: runLifecycle.ts

import { loggerMain } from "./logger";

type RunEndedListener = () => void;

const setRunEndedListener = new Set<RunEndedListener>();

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
      loggerMain.error(
        `Run-ended listener failed: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  }
}
