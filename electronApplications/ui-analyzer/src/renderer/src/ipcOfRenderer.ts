// FileName: ipcOfRenderer.ts
import io from "socket.io-client";

import { useSettingStore, useInformationStore, useSelectorStore } from "./store";
import { removePrefix } from "./attrHandleFunc";
import type {
  DictInvokeResult,
  DictEleTreeItem,
  RendererLogLevel,
  MainInvokeCommand,
} from "../../shared/interface";

function formatLogMessage(message: unknown): string {
  if (typeof message === "string") {
    return message;
  }

  if (message instanceof Error) {
    return message.stack ?? message.message;
  }

  try {
    return JSON.stringify(message);
  } catch {
    return String(message);
  }
}

const sendLogToMain = (level: RendererLogLevel, message: unknown): void => {
  // Log to Electron console.
  const formattedMessage = formatLogMessage(message);

  console.log(`[${level}] ${formattedMessage}`);
  window.uiAnalyzer.logToMain(level, formattedMessage);
};

export const loggerRenderer = {
  error: (message: unknown) => sendLogToMain("error", message),
  warn: (message: unknown) => sendLogToMain("warn", message),
  info: (message: unknown) => sendLogToMain("info", message),
  http: (message: unknown) => sendLogToMain("http", message),
  verbose: (message: unknown) => sendLogToMain("verbose", message),
  debug: (message: unknown) => sendLogToMain("debug", message),
  silly: (message: unknown) => sendLogToMain("silly", message),
};

export async function invokeMain(
  command: MainInvokeCommand,
  data?: unknown,
): Promise<unknown | undefined> {
  // loggerRenderer.debug("--invokeMain--");
  const result: DictInvokeResult = await window.uiAnalyzer.invokeMain(command, data);

  if (result.success) {
    return result.data;
  }

  const informationStore = useInformationStore();
  informationStore.showAlertMessage(JSON.stringify(result.data));
  return undefined;
}

window.uiAnalyzer.onInitSetting((data) => {
  loggerRenderer.debug(
    `[send-from-main]\ncommand=init-setting\ndata=${JSON.stringify(
      [data[0], "[redacted]"],
      null,
      2,
    )}`,
  );

  const settingStore = useSettingStore();
  settingStore.initializeSetting(data);
});

/* Create socket. */
let socket: ReturnType<typeof io> | null = null;

export function connectToServer(port: number, token: string): void {
  const settingStore = useSettingStore();

  if (socket && socket.connected) {
    loggerRenderer.debug("Socket.IO already connected: " + socket.id);
    return;
  }

  if (socket) {
    socket.removeAllListeners();
    socket.disconnect();
    socket = null;
  }

  socket = io(`http://127.0.0.1:${port}`, {
    transports: ["websocket"],
    auth: {
      clientType: "uiAnalyzer",
      token: token,
    },
  });

  socket.on("connect", () => {
    loggerRenderer.debug("Socket.IO connection established: " + socket?.id);
    settingStore.socketState = true;
    void invokeMain("cmd-toggle-socket-status", true);
  });

  socket.on("disconnect", () => {
    loggerRenderer.debug("Socket.IO connection disconnected");
    settingStore.socketState = false;
    void invokeMain("cmd-toggle-socket-status", false);
  });

  socket.on("connect_error", (e: Error) => {
    console.error("Socket.IO connection error:", e);
    settingStore.socketState = false;
    void invokeMain("cmd-toggle-socket-status", false);
  });

  socket.on("message_flask_to_uianalyzer", (data: string) => {
    // settingStore.socketState = true;
    loggerRenderer.debug("--message_flask_to_uianalyzer--");
    // loggerRenderer.debug(data);
    const selectorStore = useSelectorStore();

    if (data.startsWith("Element_Tree:")) {
      data = removePrefix(data, "Element_Tree:");

      // Simple type guard.
      try {
        const parsedData: unknown = JSON.parse(data);

        if (!Array.isArray(parsedData)) {
          throw new Error("Element tree result is not an array.");
        }

        const dictResult = parsedData as [DictEleTreeItem[], number[], number];

        selectorStore.arrEleTree = dictResult[0];
        selectorStore.arrEleTreeOpened = dictResult[1];
        selectorStore.intEleTreeActivated = dictResult[2];
        selectorStore.updateEleTreeSelector();
      } catch (e) {
        const informationStore = useInformationStore();
        informationStore.showAlertMessage(
          e instanceof Error ? e.message : "Failed to parse Local Server response.",
        );
      }
    } else {
      try {
        const parsedData: unknown = JSON.parse(data);

        if (
          typeof parsedData !== "object" ||
          parsedData === null ||
          !("data" in parsedData)
        ) {
          throw new Error("Local Server response does not contain data.");
        }

        const dictResult = parsedData as Record<string, unknown>;

        const informationStore = useInformationStore();
        informationStore.information = JSON.stringify(dictResult["data"]);
        selectorStore.processDescription = "Idle";
      } catch (e) {
        const informationStore = useInformationStore();
        informationStore.showAlertMessage(
          e instanceof Error ? e.message : "Failed to parse Local Server response.",
        );
        selectorStore.processDescription = "Idle";
      }
    }
  });
}

export function sendCmdToFlask(dictCommand: Record<string, unknown>): void {
  loggerRenderer.debug("--sendCmdToFlask--");

  // Prevent command cache to be executed after reconnection.
  if (!socket || !socket.connected) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage("Local Server is not connected.");
    return;
  }

  socket.emit("uianalyzer_command", JSON.stringify(dictCommand));
}
