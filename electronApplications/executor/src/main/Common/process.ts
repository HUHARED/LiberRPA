// FileName: process.ts

import type { ChildProcess } from "child_process";

export function isProcessRunning(processObj: ChildProcess): boolean {
  return processObj.exitCode === null && processObj.signalCode === null;
}
