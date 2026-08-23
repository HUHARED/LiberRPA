// FileName: index.d.ts

import type { ExecutorPreloadApi } from "../shared/ipc";

declare global {
  interface Window {
    executor: ExecutorPreloadApi;
  }
}
