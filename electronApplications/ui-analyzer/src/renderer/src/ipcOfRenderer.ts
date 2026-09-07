// FileName: ipcOfRenderer.ts

import io from "socket.io-client";

import { loggerRenderer } from "./logger";
import {
  isDictForUiAnalyzer,
  isElementTreeResult,
  isValidateResult,
  parseUiAnalyzerServerMessage,
} from "./localServerProtocol";
import {
  useInformationStore,
  useOperationStore,
  useSelectorStore,
  useSettingStore,
} from "./store";
import type {
  DictInvokeResult,
  MainInvokeCommand,
  UiAnalyzerOperationName,
  UiAnalyzerServerMessage,
} from "../../shared/interface";

export async function invokeMain(
  command: MainInvokeCommand,
  data?: unknown,
): Promise<boolean> {
  try {
    const result: DictInvokeResult = await window.uiAnalyzer.invokeMain(command, data);

    if (result.success) {
      return true;
    }

    const informationStore = useInformationStore();
    informationStore.showAlertMessage(result.data);
    return false;
  } catch (e) {
    const strErrorMessage =
      e instanceof Error
        ? e.message
        : "Failed to communicate with UI Analyzer Main Process.";
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(strErrorMessage);
    return false;
  }
}

window.uiAnalyzer.onInitSetting((data) => {
  loggerRenderer.debug(
    `[send-from-main]\ncommand=init-setting\ndata=${JSON.stringify(
      { ...data, token: "[redacted]" },
      null,
      2,
    )}`,
  );

  const settingStore = useSettingStore();
  settingStore.initializeSetting(data);
  connectToServer(data.localServerPort, data.token);
});

let socket: ReturnType<typeof io> | null = null;
let promiseMessageHandling: Promise<void> = Promise.resolve();

async function restoreOperationWindow(intOperationId: number): Promise<void> {
  const operationStore = useOperationStore();
  if (
    !operationStore.isCurrentOperation(intOperationId) ||
    !operationStore.boolWindowRestoreRequired
  ) {
    return;
  }

  loggerRenderer.debug(`Restore UI Analyzer for operation ${intOperationId}.`);
  const boolRestored = await invokeMain("cmd-restore-window");
  if (boolRestored) {
    operationStore.markWindowRestored(intOperationId);
  }
}

async function finishOperation(intOperationId: number): Promise<void> {
  const operationStore = useOperationStore();
  if (!operationStore.isCurrentOperation(intOperationId)) {
    return;
  }

  await restoreOperationWindow(intOperationId);
  operationStore.finishOperation(intOperationId);
}

async function interruptActiveOperation(strMessage: string): Promise<void> {
  const operationStore = useOperationStore();
  const intOperationId = operationStore.intActiveOperationId;
  if (intOperationId === undefined) {
    return;
  }

  const informationStore = useInformationStore();
  informationStore.resetSelectorValidation();
  informationStore.information = strMessage;
  informationStore.showAlertMessage(strMessage);
  await finishOperation(intOperationId);
}

async function handleOperationResult(
  message: Extract<UiAnalyzerServerMessage, { messageType: "operationResult" }>,
): Promise<void> {
  const operationStore = useOperationStore();
  if (!operationStore.isCurrentOperation(message.operationId)) {
    loggerRenderer.debug(
      `Ignore operation result for inactive operation ${message.operationId}.`,
    );
    return;
  }

  const operationName = operationStore.operationName;
  if (operationName === undefined) {
    return;
  }

  const informationStore = useInformationStore();
  const selectorStore = useSelectorStore();

  if (!message.boolSuccess) {
    const strErrorMessage = message.data as string;
    informationStore.resetSelectorValidation();
    informationStore.information = strErrorMessage;
    informationStore.showAlertMessage(strErrorMessage);
    await restoreOperationWindow(message.operationId);
    return;
  }

  if (message.data === null) {
    informationStore.resetSelectorValidation();
    informationStore.information = "The operation was canceled.";
    await restoreOperationWindow(message.operationId);
    return;
  }

  if (operationName === "validate") {
    if (!isValidateResult(message.data)) {
      throw new Error("Local Server returned an invalid validation result.");
    }

    const boolResultApplied = informationStore.applySelectorValidationResult(
      message.data.validate,
      selectorStore.strJsonText,
    );
    if (boolResultApplied) {
      informationStore.information = message.data.validate
        ? "The Selector matched the target element."
        : "The Selector did not match a target element.";
    } else {
      informationStore.information =
        "The Selector changed during validation. Validate the current Selector again.";
    }
    await restoreOperationWindow(message.operationId);
    return;
  }

  if (!isDictForUiAnalyzer(message.data)) {
    throw new Error("Local Server returned an invalid indication result.");
  }

  selectorStore.applyIndicateResult(message.data);
  informationStore.information = "The Selector was received.";

  if (operationName === "indicate_uia" || operationName === "indicate_chrome") {
    operationStore.markBuildingElementTree(message.operationId);
  }

  await restoreOperationWindow(message.operationId);
}

function handleElementTreeResult(
  message: Extract<UiAnalyzerServerMessage, { messageType: "elementTreeResult" }>,
): void {
  const operationStore = useOperationStore();
  if (!operationStore.isCurrentOperation(message.operationId)) {
    loggerRenderer.debug(
      `Ignore Element Tree result for inactive operation ${message.operationId}.`,
    );
    return;
  }

  if (
    operationStore.operationPhase !== "buildingElementTree" ||
    (operationStore.operationName !== "indicate_uia" &&
      operationStore.operationName !== "indicate_chrome")
  ) {
    throw new Error("Local Server returned an unexpected Element Tree result.");
  }

  const informationStore = useInformationStore();
  if (!message.boolSuccess) {
    const strErrorMessage = message.data as string;
    informationStore.information = strErrorMessage;
    informationStore.showAlertMessage(strErrorMessage);
    return;
  }

  if (!isElementTreeResult(message.data)) {
    throw new Error("Local Server returned an invalid Element Tree result.");
  }

  const selectorStore = useSelectorStore();
  selectorStore.applyElementTreeResult(message.data);
  informationStore.information = "The Element Tree was received.";
}

async function handleUiAnalyzerServerMessage(data: unknown): Promise<void> {
  let message: UiAnalyzerServerMessage;
  try {
    message = parseUiAnalyzerServerMessage(data);
  } catch (e) {
    const strErrorMessage =
      e instanceof Error ? e.message : "Failed to parse Local Server response.";
    loggerRenderer.error(strErrorMessage);
    await interruptActiveOperation(strErrorMessage);
    return;
  }

  try {
    switch (message.messageType) {
      case "operationResult":
        await handleOperationResult(message);
        return;

      case "elementTreeResult":
        handleElementTreeResult(message);
        return;

      case "operationCompleted":
        await finishOperation(message.operationId);
        return;
    }
  } catch (e) {
    const strErrorMessage =
      e instanceof Error ? e.message : "Failed to handle Local Server response.";
    loggerRenderer.error(strErrorMessage);

    const operationStore = useOperationStore();
    if (operationStore.isCurrentOperation(message.operationId)) {
      const informationStore = useInformationStore();
      informationStore.resetSelectorValidation();
      informationStore.information = strErrorMessage;
      informationStore.showAlertMessage(strErrorMessage);
      await finishOperation(message.operationId);
    }
  }
}

function queueUiAnalyzerServerMessage(data: unknown): void {
  promiseMessageHandling = promiseMessageHandling
    .then(() => handleUiAnalyzerServerMessage(data))
    .catch((e: unknown) => {
      loggerRenderer.error(e);
    });
}

export function connectToServer(port: number, token: string): void {
  const settingStore = useSettingStore();

  if (socket?.connected) {
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
      token,
    },
  });

  socket.on("connect", () => {
    loggerRenderer.debug("Socket.IO connection established: " + socket?.id);
    settingStore.socketState = true;
    void invokeMain("cmd-toggle-socket-status", true);
  });

  socket.on("disconnect", () => {
    loggerRenderer.debug("Socket.IO connection disconnected.");
    settingStore.socketState = false;
    void invokeMain("cmd-toggle-socket-status", false);
    void interruptActiveOperation("Local Server disconnected during the operation.");
  });

  socket.on("connect_error", (e: Error) => {
    loggerRenderer.error(e);
    settingStore.socketState = false;
    void invokeMain("cmd-toggle-socket-status", false);
    void interruptActiveOperation(
      "Failed to connect to Local Server during the operation.",
    );
  });

  socket.on("message_flask_to_uianalyzer", queueUiAnalyzerServerMessage);
}

export interface StartUiAnalyzerOperationOptions {
  minimizeWindow?: boolean;
  validateSelectorText?: string;
}

export async function startUiAnalyzerOperation(
  operationName: UiAnalyzerOperationName,
  dictCommandData: Record<string, unknown>,
  options: StartUiAnalyzerOperationOptions = {},
): Promise<boolean> {
  const informationStore = useInformationStore();
  const operationStore = useOperationStore();
  const settingStore = useSettingStore();

  if (!socket?.connected) {
    const strMessage = "Local Server is not connected.";
    informationStore.information = strMessage;
    informationStore.showAlertMessage(strMessage);
    return false;
  }

  if (operationStore.isBusy) {
    informationStore.showAlertMessage("Another UI Analyzer operation is still running.");
    return false;
  }

  let intOperationId: number;
  try {
    intOperationId = operationStore.beginOperation(operationName);
  } catch (e) {
    informationStore.showAlertMessage(e instanceof Error ? e.message : String(e));
    return false;
  }

  if (options.validateSelectorText !== undefined) {
    informationStore.startSelectorValidation(options.validateSelectorText);
  }
  informationStore.information = "Waiting for Local Server.";

  const boolShouldMinimize =
    options.minimizeWindow !== false && settingStore.minimizeWindow;
  if (boolShouldMinimize) {
    // Mark the restore requirement before awaiting IPC so disconnect handling cannot miss it.
    operationStore.markWindowRestoreRequired(intOperationId);
    loggerRenderer.debug(`Minimize UI Analyzer for operation ${intOperationId}.`);
    const boolMinimized = await invokeMain("cmd-minimize-window");
    if (!boolMinimized) {
      informationStore.resetSelectorValidation();
      operationStore.markWindowRestored(intOperationId);
      operationStore.finishOperation(intOperationId);
      return false;
    }
  }

  if (!socket?.connected) {
    await interruptActiveOperation(
      "Local Server disconnected before the command was sent.",
    );
    return false;
  }

  try {
    socket.emit(
      "uianalyzer_command",
      JSON.stringify({
        ...dictCommandData,
        operationId: intOperationId,
        commandName: operationName,
      }),
    );
    loggerRenderer.debug(`Sent UI Analyzer operation ${intOperationId}: ${operationName}`);
    return true;
  } catch (e) {
    const strErrorMessage =
      e instanceof Error ? e.message : "Failed to send command to Local Server.";
    await interruptActiveOperation(strErrorMessage);
    return false;
  }
}
