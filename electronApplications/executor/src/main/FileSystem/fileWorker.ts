// FileName: fileWorker.ts

import { Worker } from "worker_threads";

const abortFileWork = new AbortController();
let promiseFileWork: Promise<void> = Promise.resolve();

export function runFileWorker<Args extends object>(
  workerPath: string,
  args: Args,
  signal?: AbortSignal,
): Promise<void> {
  const taskSignal = signal
    ? AbortSignal.any([abortFileWork.signal, signal])
    : abortFileWork.signal;
  // Archive libraries hold whole files in memory; do not overlap heavy file tasks.
  const promiseTask = promiseFileWork.then(() => {
    taskSignal.throwIfAborted();
    return new Promise<void>((resolve, reject) => {
      const workerObj = new Worker(workerPath, { workerData: args });
      let errorObj: Error | undefined;
      function abortWorker(): void {
        void workerObj.terminate().catch((e: unknown) => {
          errorObj = e instanceof Error ? e : new Error(String(e));
        });
      }
      taskSignal.addEventListener("abort", abortWorker, { once: true });
      workerObj.once("error", (e: Error) => {
        errorObj = e;
      });
      // Wait for exit even on failure, so callers can safely remove temporary files.
      workerObj.once("exit", (exitCode: number) => {
        taskSignal.removeEventListener("abort", abortWorker);
        if (taskSignal.aborted) reject(taskSignal.reason);
        else if (errorObj) reject(errorObj);
        else if (exitCode !== 0)
          reject(new Error(`File worker exited with code ${exitCode}.`));
        else resolve();
      });
    });
  });
  // One failure must not prevent unrelated file work from starting.
  promiseFileWork = promiseTask.catch(() => {});
  return promiseTask;
}

export function stopFileWorkers(): Promise<void> {
  abortFileWork.abort(new Error("Executor is shutting down."));
  return promiseFileWork;
}
