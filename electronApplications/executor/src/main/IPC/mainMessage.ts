// FileName: mainMessage.ts

import type { WebContents } from "electron";

import { IPC_CHANNEL_MAIN_MESSAGE } from "../../shared/ipc";
import type { Dict_Message_Main } from "../../shared/ipc";

export function sendMainMessage(
  webContentsObj: WebContents,
  message: Dict_Message_Main,
): void {
  if (!webContentsObj.isDestroyed()) {
    webContentsObj.send(IPC_CHANNEL_MAIN_MESSAGE, message);
  }
}
