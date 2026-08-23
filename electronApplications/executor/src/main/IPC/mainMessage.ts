import type { WebContents } from "electron";

import { IPC_CHANNEL_MAIN_MESSAGE } from "../../shared/ipc";
import type { DictMainMessage } from "../../shared/ipc";

export function sendMainMessage(
  webContentsObj: WebContents,
  message: DictMainMessage,
): void {
  if (!webContentsObj.isDestroyed()) {
    webContentsObj.send(IPC_CHANNEL_MAIN_MESSAGE, message);
  }
}
