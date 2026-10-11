// FileName: mainMessage.ts

import type { WebContents } from "electron";

import { IPC_CHANNEL_MAIN_MESSAGE } from "../../shared/ipc";
import type { MainMessage } from "../../shared/ipc";

export function sendMainMessage(webContentsObj: WebContents, message: MainMessage): void {
  if (!webContentsObj.isDestroyed()) {
    webContentsObj.send(IPC_CHANNEL_MAIN_MESSAGE, message);
  }
}
