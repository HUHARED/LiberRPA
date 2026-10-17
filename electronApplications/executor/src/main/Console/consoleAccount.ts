// FileName: consoleAccount.ts

import { app, safeStorage } from "electron";
import fs from "fs";
import os from "os";
import path from "path";

import {
  ConsoleConnection,
  type ConsoleSessionInfo,
  type ConsoleExecutorPage,
  type ConsoleSignInArgs,
  type ConsoleAccountState,
} from "../../shared/consoleAccount";
import { getErrorMessage } from "../../shared/error";
import { readJsonFile, writeJsonFileAtomic } from "../Common/jsonFile";
import { ensureRecord, ensureString, ensureNonEmptyString } from "../Common/validation";
import {
  hasActiveRun,
  beginConsoleAccountTransition,
  endConsoleAccountTransition,
} from "../Run/packageRunner";
import {
  ConsoleRequestError,
  normalizeConsoleUrl,
  requestConsole,
  parseConsoleSession,
  parseConsoleHeartbeat,
  parseExecutorChoices,
} from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import {
  ConsoleControlMessage,
  startConsoleControl,
  stopConsoleControl,
} from "./consoleControl";

let strConsoleUrl = "";
let strRememberedEmail = "";
let strToken = "";
let sessionInfo: ConsoleSessionInfo | null = null;
let connection = ConsoleConnection.SignedOut;
let strMessage = "";
let boolBusy = false;
let boolStopped = false;
let promiseContact: Promise<void> | undefined;
let promiseOperation: Promise<unknown> | undefined;
let publishState: (() => void) | undefined;

function getCredentialPath(): string {
  return path.join(app.getPath("userData"), "console-account.json");
}

function writeAccount(consoleUrl: string, token: string, email: string): void {
  if (token !== "" && !safeStorage.isEncryptionAvailable()) {
    throw new Error("Windows protected credential storage is unavailable.");
  }
  const strFilePath = getCredentialPath();
  fs.mkdirSync(path.dirname(strFilePath), { recursive: true });
  writeJsonFileAtomic(strFilePath, {
    consoleUrl,
    email,
    encryptedToken: token === "" ? "" : safeStorage.encryptString(token).toString("base64"),
  });
}

function clearSession(message = ""): void {
  stopConsoleControl();
  strToken = "";
  sessionInfo = null;
  connection = ConsoleConnection.SignedOut;
  strMessage = message;
  writeAccount(strConsoleUrl, "", strRememberedEmail);
}

function isInvalidSession(e: unknown): boolean {
  return (
    e instanceof ConsoleRequestError &&
    e.status === 401 &&
    e.code === "executor_authentication_required"
  );
}

function updateSession(response: Record<string, unknown>): ConsoleSessionInfo {
  sessionInfo =
    response.type === ConsoleControlMessage.Heartbeat
      ? parseConsoleHeartbeat(response, sessionInfo)
      : parseConsoleSession(response);
  connection = sessionInfo.session.selection_required
    ? ConsoleConnection.SelectingExecutor
    : ConsoleConnection.Connected;
  strMessage = "";
  return sessionInfo;
}

function handleContactError(e: unknown): void {
  if (isInvalidSession(e)) {
    clearSession(
      "The Console session or Executor association is no longer valid. Sign in again.",
    );
    return;
  }
  // Keep a confirmed denial until Console accepts the session again.
  if (
    connection === ConsoleConnection.AccessUnavailable &&
    !(e instanceof ConsoleRequestError && e.status === 403)
  )
    return;
  strMessage = getErrorMessage(e);
  connection =
    e instanceof ConsoleRequestError && e.status === 403
      ? ConsoleConnection.AccessUnavailable
      : ConsoleConnection.Reconnecting;
}

async function revokeSession(): Promise<void> {
  if (strToken === "") {
    return;
  }
  try {
    await requestConsole(strConsoleUrl, "executor/logout/", strToken, {});
  } catch (e: unknown) {
    if (!isInvalidSession(e)) {
      throw e;
    }
  }
}

async function contactConsole(): Promise<void> {
  try {
    const dictResponse = await requestConsole(strConsoleUrl, "executor/session/", strToken);
    updateSession(dictResponse);
  } catch (e: unknown) {
    if (e instanceof ConsoleRequestError && e.code === "executor_selection_required") {
      // A restarted login must finish selecting or cancel; it is never an everyday account state.
      try {
        const dictResponse = await requestConsole(
          strConsoleUrl,
          "executor/choices/",
          strToken,
        );
        updateSession(dictResponse);
      } catch (e: unknown) {
        handleContactError(e);
      }
    } else {
      handleContactError(e);
    }
  } finally {
    publishState?.();
    refreshConsoleControl();
  }
}

function refreshConsoleControl(): void {
  if (
    boolStopped ||
    boolBusy ||
    strToken === "" ||
    sessionInfo?.session.selection_required
  ) {
    if (boolStopped || strToken === "" || sessionInfo?.session.selection_required)
      stopConsoleControl();
    return;
  }
  const credential = { consoleUrl: strConsoleUrl, token: strToken };
  startConsoleControl(
    credential,
    (response) => {
      if (credential.token !== strToken || credential.consoleUrl !== strConsoleUrl) return;
      updateSession(response);
      publishState?.();
    },
    (e) => {
      if (credential.token !== strToken || credential.consoleUrl !== strConsoleUrl) return;
      if (e instanceof ConsoleRequestError && e.code === "executor_selection_required") {
        stopConsoleControl();
        requestConsoleContact();
      } else {
        handleContactError(e);
        publishState?.();
      }
    },
  );
}

function requestConsoleContact(): void {
  if (
    boolStopped ||
    boolBusy ||
    promiseContact !== undefined ||
    strToken === "" ||
    sessionInfo?.session.selection_required
  ) {
    return;
  }

  promiseContact = contactConsole()
    .catch((e: unknown) => {
      strMessage = getErrorMessage(e);
      publishState?.();
    })
    .finally(() => {
      promiseContact = undefined;
    });
}

async function runAccountOperation<T>(operation: () => Promise<T>): Promise<T> {
  if (boolBusy || boolStopped) {
    throw new Error("Wait for the current Console operation to finish.");
  }

  boolBusy = true;
  publishState?.();
  const promiseResult = (async (): Promise<T> => {
    await promiseContact;
    return await operation();
  })();
  promiseOperation = promiseResult;
  try {
    return await promiseResult;
  } finally {
    boolBusy = false;
    promiseOperation = undefined;
    refreshConsoleControl();
    publishState?.();
  }
}

export function getConsoleAccountState(): ConsoleAccountState {
  return {
    consoleUrl: strConsoleUrl,
    rememberedEmail: strRememberedEmail,
    connection,
    sessionInfo,
    message: strMessage,
    hasCredential: strToken !== "",
    hasActiveRun: hasActiveRun(),
    busy: boolBusy,
  };
}

export function getConsolePythonCredential(): ConsoleCredentialSnapshot | null {
  if (boolStopped || strToken === "" || sessionInfo?.session.selection_required) {
    return null;
  }

  // URL validation does not change the credential, even while the account UI is busy.
  // Only the private Python bridge receives this snapshot; never send it to Renderer.
  return { consoleUrl: strConsoleUrl, token: strToken };
}

async function runAccountStateOperation(
  operation: () => Promise<void>,
): Promise<ConsoleAccountState> {
  await runAccountOperation(operation);
  return getConsoleAccountState();
}

export function startConsoleAccount(onChanged: () => void): void {
  publishState = onChanged;
  try {
    const strFilePath = getCredentialPath();
    if (fs.existsSync(strFilePath)) {
      const dictAccount = ensureRecord(
        readJsonFile(strFilePath, "Console account"),
        "Console account",
      );
      const strSavedUrl = ensureString(dictAccount.consoleUrl, "Console URL");
      strConsoleUrl = strSavedUrl === "" ? "" : normalizeConsoleUrl(strSavedUrl);
      strRememberedEmail = ensureString(dictAccount.email, "Remembered email");
      const strEncryptedToken = ensureString(
        dictAccount.encryptedToken,
        "Protected credential",
      );
      if (strEncryptedToken !== "") {
        if (!safeStorage.isEncryptionAvailable()) {
          throw new Error("Windows protected credential storage is unavailable.");
        }
        strToken = safeStorage.decryptString(Buffer.from(strEncryptedToken, "base64"));
        connection = ConsoleConnection.Reconnecting;
      }
    }
  } catch {
    strMessage =
      "The saved Console account could not be opened. Check Windows credential storage and sign in again if needed.";
  }
  publishState();
  requestConsoleContact();
}

export async function saveConsoleAddress(consoleUrl: string): Promise<ConsoleAccountState> {
  return await runAccountStateOperation(async () => {
    const strNewUrl = normalizeConsoleUrl(consoleUrl);
    const dictInfo = await requestConsole(strNewUrl, "info/");
    if (dictInfo.product !== "LiberRPA Console" || dictInfo.protocol_version !== 1) {
      throw new Error("This address is not a compatible LiberRPA Console.");
    }
    if (strNewUrl === strConsoleUrl) {
      return;
    }

    beginConsoleAccountTransition();
    stopConsoleControl();
    try {
      // Only the old address receives the old credential, after anonymous validation succeeds.
      await revokeSession();
      writeAccount(strNewUrl, "", "");
      strConsoleUrl = strNewUrl;
      strRememberedEmail = "";
      strToken = "";
      sessionInfo = null;
      connection = ConsoleConnection.SignedOut;
      strMessage = "Console address saved. Sign in to connect.";
    } finally {
      endConsoleAccountTransition();
    }
  });
}

export async function signInConsole(args: ConsoleSignInArgs): Promise<ConsoleAccountState> {
  return await runAccountStateOperation(async () => {
    if (strConsoleUrl === "") {
      throw new Error("Validate and save the Console address first.");
    }
    if (strToken !== "") {
      throw new Error("Finish or cancel the existing Console login first.");
    }
    if (!safeStorage.isEncryptionAvailable()) {
      throw new Error("Windows protected credential storage is unavailable.");
    }
    const dictResponse = await requestConsole(strConsoleUrl, "executor/login/", "", {
      email: args.email.trim(),
      password: args.password,
      computer_name: os.hostname(),
      client_version: app.getVersion(),
    });
    const strNewToken = ensureNonEmptyString(dictResponse.token, "Console token");
    if (!/^lrex_[A-Za-z0-9_-]{43}$/.test(strNewToken)) {
      throw new Error("Console returned an invalid session credential.");
    }
    // Persist the protected selection credential before any association request can commit remotely.
    strToken = strNewToken;
    try {
      const loginSession = updateSession(dictResponse);
      writeAccount(strConsoleUrl, strToken, loginSession.user.email);
      strRememberedEmail = loginSession.user.email;
    } catch (e: unknown) {
      await revokeSession();
      clearSession();
      throw e;
    }
  });
}

export async function getConsoleExecutorChoices(
  page: number,
): Promise<ConsoleExecutorPage> {
  return await runAccountOperation(async () => {
    if (!sessionInfo?.session.selection_required) {
      throw new Error("Sign in before selecting an Executor.");
    }
    try {
      const dictResponse = await requestConsole(
        strConsoleUrl,
        `executor/choices/?page=${page}`,
        strToken,
      );
      updateSession(dictResponse);
      return parseExecutorChoices(dictResponse);
    } catch (e: unknown) {
      if (isInvalidSession(e)) {
        handleContactError(e);
      } else if (
        e instanceof ConsoleRequestError &&
        e.code === "executor_already_associated"
      ) {
        // A previous association response may have been lost after the server committed it.
        await contactConsole();
      }
      throw e;
    }
  });
}

export async function associateConsoleExecutor(
  executorId: string,
): Promise<ConsoleAccountState> {
  return await runAccountStateOperation(async () => {
    if (!sessionInfo?.session.selection_required) {
      throw new Error("Sign in before selecting an Executor.");
    }
    try {
      const dictResponse = await requestConsole(
        strConsoleUrl,
        "executor/associate/",
        strToken,
        {
          executor_id: executorId,
        },
      );
      updateSession(dictResponse);
    } catch (e: unknown) {
      if (isInvalidSession(e)) {
        handleContactError(e);
      }
      throw e;
    }
  });
}

export async function signOutConsole(): Promise<ConsoleAccountState> {
  return await runAccountStateOperation(async () => {
    beginConsoleAccountTransition();
    stopConsoleControl();
    try {
      await revokeSession();
      clearSession();
    } finally {
      endConsoleAccountTransition();
    }
  });
}

export async function stopConsoleAccount(): Promise<void> {
  boolStopped = true;
  stopConsoleControl();
  await Promise.allSettled([promiseContact, promiseOperation]);
  if (sessionInfo?.session.selection_required) {
    try {
      await revokeSession();
      clearSession();
    } catch {
      // Keep the protected credential so a later launch can retry cancellation or recover an association.
    }
  }
}
