// FileName: consoleControl.ts

import { getErrorMessage } from "../../shared/error";

import { ensureRecord, ensureNonEmptyString } from "../Common/validation";
import { loggerMain } from "../Logging/logger";
import { getActiveConsoleRunIds, getLocalRunningCount } from "../Run/projectRunner";
import { onRunActivityChanged } from "../Run/lifecycle";
import { getRecoveredConsoleRunIds, getOtherRecoveredRunCount } from "../Run/recoveredRuns";
import { getConsoleWorkSessionKey } from "./workRepository";
import { getLocalWaitingCount, onJobQueueChanged } from "../Scheduler/schedulerEngine";
import { ConsoleRequestError } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";

export enum ConsoleControlMessage {
  Authenticate = "authenticate",
  Ready = "ready",
  Heartbeat = "heartbeat",
  State = "state",
  WorkAvailable = "work_available",
  Error = "error",
}

const INT_HEARTBEAT_INTERVAL_MS = 15_000;
const INT_RESPONSE_TIMEOUT_MS = 45_000;
const INT_CONNECTION_TIMEOUT_MS = 10_000;
const INT_MAX_RECONNECT_DELAY_MS = 30_000;
const setWorkListener = new Set<() => void>();
const setWorkStateListener = new Set<() => void>();
let credential: ConsoleCredentialSnapshot | null = null;
let socket: WebSocket | undefined;
let timerHeartbeat: NodeJS.Timeout | undefined;
let timerConnection: NodeJS.Timeout | undefined;
let timerReconnect: NodeJS.Timeout | undefined;
let boolReady = false;
let boolStateQueued = false;
let boolUnavailableLogged = false;
let strLastWorkState = "";
let intReconnectDelayMs = 1000;
let updateSession: ((response: Record<string, unknown>) => void) | undefined;
let reportError: ((e: unknown) => void) | undefined;

export function getConsoleWorkState(): {
  running_run_ids: string[];
  local_waiting_count: number;
  local_running_count: number;
} {
  const strSessionKey = credential ? getConsoleWorkSessionKey(credential) : undefined;
  return {
    running_run_ids: [
      ...getActiveConsoleRunIds(),
      ...getRecoveredConsoleRunIds(strSessionKey),
    ],
    local_waiting_count: getLocalWaitingCount(),
    local_running_count: getLocalRunningCount() + getOtherRecoveredRunCount(strSessionKey),
  };
}

export function getConsoleControlCredential(): ConsoleCredentialSnapshot | null {
  return boolReady ? credential : null;
}

export function onConsoleWorkAvailable(listener: () => void): () => void {
  setWorkListener.add(listener);
  return () => setWorkListener.delete(listener);
}

function notifyWorkAvailable(): void {
  for (const listener of setWorkListener) listener();
}

export function onConsoleWorkStateReported(listener: () => void): () => void {
  setWorkStateListener.add(listener);
  return () => setWorkStateListener.delete(listener);
}

function notifyWorkStateReported(): void {
  for (const listener of setWorkStateListener) listener();
}

function publishConsoleWorkState(): void {
  if (boolStateQueued || !boolReady) return;
  boolStateQueued = true;
  queueMicrotask(() => {
    boolStateQueued = false;
    if (!boolReady || socket?.readyState !== WebSocket.OPEN) return;
    const workState = getConsoleWorkState();
    const strWorkState = JSON.stringify(workState);
    if (strWorkState === strLastWorkState) return;
    strLastWorkState = strWorkState;
    socket.send(JSON.stringify({ type: ConsoleControlMessage.State, ...workState }));
  });
}

export function stopConsoleControl(): void {
  credential = null;
  boolReady = false;
  clearTimeout(timerReconnect);
  clearTimeout(timerConnection);
  clearInterval(timerHeartbeat);
  const previousSocket = socket;
  socket = undefined;
  previousSocket?.close();
}

function connectConsoleControl(): void {
  if (!credential) return;
  const currentCredential = credential;
  const urlObj = new URL("/api/clients/executor/control/", currentCredential.consoleUrl);
  urlObj.protocol = urlObj.protocol === "https:" ? "wss:" : "ws:";
  const currentSocket = new WebSocket(urlObj);
  socket = currentSocket;
  let boolErrorReported = false;
  let intRetryAfterMs = 0;
  let intLastResponseAt = Date.now();

  function failConnection(e: unknown): void {
    if (socket !== currentSocket) return;
    boolReady = false;
    if (!boolErrorReported) {
      boolErrorReported = true;
      if (!boolUnavailableLogged) {
        boolUnavailableLogged = true;
        loggerMain.warn(`Console control connection unavailable: ${getErrorMessage(e)}`);
      }
      reportError?.(e);
    }
    if (socket !== currentSocket || credential !== currentCredential) return;
    // A broken network may never complete a close handshake; reconnect independently.
    socket = undefined;
    clearTimeout(timerConnection);
    clearInterval(timerHeartbeat);
    const intDelayMs = Math.max(
      intRetryAfterMs,
      Math.round(intReconnectDelayMs * (0.8 + Math.random() * 0.4)),
    );
    intReconnectDelayMs = Math.min(intReconnectDelayMs * 2, INT_MAX_RECONNECT_DELAY_MS);
    timerReconnect = setTimeout(connectConsoleControl, intDelayMs);
    currentSocket.close();
  }

  timerConnection = setTimeout(() => {
    failConnection(new Error("Console did not establish its control connection in time."));
  }, INT_CONNECTION_TIMEOUT_MS);

  currentSocket.addEventListener("open", () => {
    if (socket !== currentSocket) return;
    const workState = getConsoleWorkState();
    strLastWorkState = JSON.stringify(workState);
    currentSocket.send(
      JSON.stringify({
        type: ConsoleControlMessage.Authenticate,
        token: currentCredential.token,
        ...workState,
      }),
    );
  });
  currentSocket.addEventListener("message", (event) => {
    if (socket !== currentSocket) return;
    try {
      if (typeof event.data !== "string")
        throw new Error("Console returned an invalid control message.");
      const response = ensureRecord(JSON.parse(event.data) as unknown, "Control message");
      if (response.type === ConsoleControlMessage.Error) {
        if (typeof response.retry_after === "number" && response.retry_after > 0)
          intRetryAfterMs = response.retry_after * 1000;
        throw new ConsoleRequestError(
          ensureNonEmptyString(response.message, "Control error message"),
          typeof response.status === "number" ? response.status : 500,
          ensureNonEmptyString(response.code, "Control error code"),
        );
      }
      if (
        response.type === ConsoleControlMessage.Ready ||
        response.type === ConsoleControlMessage.Heartbeat
      ) {
        updateSession?.(response);
        if (socket !== currentSocket) return;
        intLastResponseAt = Date.now();
        if (response.type === ConsoleControlMessage.Ready) {
          clearTimeout(timerConnection);
          boolReady = true;
          intReconnectDelayMs = 1000;
          boolUnavailableLogged = false;
          loggerMain.info("Console control connection established.");
          timerHeartbeat = setInterval(() => {
            if (socket !== currentSocket || !boolReady) return;
            if (Date.now() - intLastResponseAt >= INT_RESPONSE_TIMEOUT_MS) {
              failConnection(
                new Error("Console stopped responding to the control heartbeat."),
              );
              return;
            }
            const workState = getConsoleWorkState();
            strLastWorkState = JSON.stringify(workState);
            currentSocket.send(
              JSON.stringify({
                type: ConsoleControlMessage.Heartbeat,
                ...workState,
              }),
            );
          }, INT_HEARTBEAT_INTERVAL_MS);
          notifyWorkAvailable();
        }
        notifyWorkStateReported();
      } else if (response.type === ConsoleControlMessage.State) {
        intLastResponseAt = Date.now();
        notifyWorkStateReported();
      } else if (response.type === ConsoleControlMessage.WorkAvailable && boolReady) {
        notifyWorkAvailable();
      } else {
        throw new Error("Console returned an unsupported control message.");
      }
    } catch (e: unknown) {
      failConnection(e);
    }
  });
  currentSocket.addEventListener("error", () => {
    failConnection(new Error("Cannot reach the Console control connection."));
  });
  currentSocket.addEventListener("close", () => {
    failConnection(new Error("The Console control connection closed. Reconnecting."));
  });
}

export function startConsoleControl(
  currentCredential: ConsoleCredentialSnapshot,
  onSession: (response: Record<string, unknown>) => void,
  onError: (e: unknown) => void,
): void {
  if (
    credential?.consoleUrl === currentCredential.consoleUrl &&
    credential.token === currentCredential.token
  )
    return;
  stopConsoleControl();
  credential = currentCredential;
  updateSession = onSession;
  reportError = onError;
  intReconnectDelayMs = 1000;
  boolUnavailableLogged = false;
  connectConsoleControl();
}

onRunActivityChanged(publishConsoleWorkState);
onJobQueueChanged(publishConsoleWorkState);
