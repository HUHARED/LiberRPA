// FileName: vscodeApi.ts

import type { WebviewToExtensionMessage } from "./webviewMessages";

interface VsCodeApi {
  postMessage(message: WebviewToExtensionMessage): void;
  getState<T>(): T | undefined;
  setState<T>(state: T): void;
}

declare function acquireVsCodeApi(): VsCodeApi;

const vscodeApi = acquireVsCodeApi();

export function postMessage(message: WebviewToExtensionMessage): void {
  vscodeApi.postMessage(message);
}

export function getState<T>(): T | undefined {
  return vscodeApi.getState<T>();
}

export function setState<T>(state: T): void {
  vscodeApi.setState(state);
}
