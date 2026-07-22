// FileName: vscodeApi.ts

import type { DictMessage_WebviewToExtension } from "./extensionMessages";

interface VsCodeApi {
  postMessage(message: DictMessage_WebviewToExtension): void;
}

declare function acquireVsCodeApi(): VsCodeApi;

const vscodeApi = acquireVsCodeApi();

export function postMessage(message: DictMessage_WebviewToExtension): void {
  vscodeApi.postMessage(message);
}
