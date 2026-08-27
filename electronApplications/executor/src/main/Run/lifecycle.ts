// FileName: lifecycle.ts

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
      loggerMain.error(
        `Run-ended listener failed: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  }
}
