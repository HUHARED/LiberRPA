// FileName: commonFunc.ts

import { outputChannel } from "./commonValue";

export function printUserCanceled(): void {
  outputChannel.appendLine("User canceled.");
}
