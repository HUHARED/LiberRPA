// FileName: consoleEvents.ts

import { getErrorMessage } from "../../shared/error";

import { ensureRecord, ensureString, ensureNonEmptyString } from "../Common/validation";
import { loggerMain } from "../Logging/logger";
import { ConsoleRequestError, requestConsole } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import {
  getConsoleControlCredential,
  isCurrentConsoleControlCredential,
} from "./consoleControl";
import { getConsoleWorkSessionKey } from "./workRepository";
import {
  type ConsoleEventReceipt,
  onConsoleEventSaved,
  getPendingConsoleEvents,
  acknowledgeConsoleEvents,
  deleteExpiredConsoleEventDiagnostics,
} from "./eventRepository";

const INT_EVENT_MAINTENANCE_INTERVAL_MS = 60 * 60 * 1000;
const INT_EVENT_SHUTDOWN_TIMEOUT_MS = 10_000;
let timerEventRetry: NodeJS.Timeout | undefined;
let promiseEvents: Promise<void> | undefined;
let boolEventsRequested = false;
let boolEventFailureLogged = false;
let intEventRetryDelayMs = 2000;
let floatEventRetryAt = 0;
let strEventRetrySessionKey: string | undefined;
let boolStopped = true;
let stopEventListener: (() => void) | undefined;
let timerEventMaintenance: NodeJS.Timeout | undefined;

async function sendPendingConsoleEvents(
  strSessionKey: string,
  credential: ConsoleCredentialSnapshot,
  timeoutMs?: number,
): Promise<boolean> {
  const arrEvent = getPendingConsoleEvents(strSessionKey);
  if (!arrEvent.length) return false;
  const response = await requestConsole(
    credential.consoleUrl,
    "executor/work/events/",
    credential.token,
    { events: arrEvent },
    timeoutMs,
  );
  if (
    !Array.isArray(response.accepted_event_ids) ||
    !Array.isArray(response.rejected_events)
  )
    throw new Error("Console returned an invalid Run event receipt.");

  const setPendingEventId = new Set(arrEvent.map((event) => event.event_id));
  const setAcknowledgedEventId = new Set<string>();
  function parseReceiptEventId(value: unknown): string {
    const strId = ensureNonEmptyString(value, "Acknowledged event ID");
    if (!setPendingEventId.has(strId))
      throw new Error("Console acknowledged an event outside the submitted batch.");
    if (setAcknowledgedEventId.has(strId))
      throw new Error("Console acknowledged the same Run event more than once.");
    setAcknowledgedEventId.add(strId);
    return strId;
  }

  const receipt: ConsoleEventReceipt = {
    acceptedEventIds: response.accepted_event_ids.map(parseReceiptEventId),
    rejectedEvents: response.rejected_events.map((value: unknown) => {
      const rejection = ensureRecord(value, "Rejected event");
      return {
        eventId: parseReceiptEventId(rejection.event_id),
        code: ensureNonEmptyString(rejection.code, "Event rejection code"),
        message: ensureString(rejection.message, "Event rejection message"),
      };
    }),
  };
  if (setAcknowledgedEventId.size !== arrEvent.length)
    throw new Error("Console did not acknowledge every event in the submitted batch.");

  const intRejectedCount = acknowledgeConsoleEvents(strSessionKey, receipt);
  if (intRejectedCount)
    loggerMain.warn(
      `Console rejected ${intRejectedCount} Run event(s). ` +
        "The events and rejection details are retained in the local Executor database.",
    );
  return isCurrentConsoleControlCredential(credential);
}

export function requestConsoleEvents(): void {
  if (boolStopped) return;
  boolEventsRequested = true;
  const credential = getConsoleControlCredential();
  if (promiseEvents || !credential) return;
  const strSessionKey = getConsoleWorkSessionKey(credential);
  if (strEventRetrySessionKey !== strSessionKey) {
    clearTimeout(timerEventRetry);
    timerEventRetry = undefined;
    strEventRetrySessionKey = strSessionKey;
    floatEventRetryAt = 0;
    intEventRetryDelayMs = 2000;
    boolEventFailureLogged = false;
  }
  const floatRemainingMs = floatEventRetryAt - performance.now();
  if (floatRemainingMs > 0) {
    timerEventRetry ??= setTimeout(
      () => {
        timerEventRetry = undefined;
        requestConsoleEvents();
      },
      Math.min(floatRemainingMs, 2_147_483_647),
    );
    return;
  }
  clearTimeout(timerEventRetry);
  timerEventRetry = undefined;
  boolEventsRequested = false;
  // Send one bounded batch at a time without holding up control synchronization.
  promiseEvents = sendPendingConsoleEvents(strSessionKey, credential)
    .then((boolMoreEvents) => {
      boolEventsRequested ||= boolMoreEvents;
      if (!isCurrentConsoleControlCredential(credential)) return;
      intEventRetryDelayMs = 2000;
      floatEventRetryAt = 0;
      boolEventFailureLogged = false;
    })
    .catch((e: unknown) => {
      boolEventsRequested = true;
      if (!isCurrentConsoleControlCredential(credential)) return;
      const intRetryAfterMs = e instanceof ConsoleRequestError ? e.retryAfterMs : 0;
      floatEventRetryAt =
        performance.now() + Math.max(intEventRetryDelayMs, intRetryAfterMs);
      intEventRetryDelayMs = Math.min(intEventRetryDelayMs * 2, 30_000);
      if (!boolEventFailureLogged) {
        boolEventFailureLogged = true;
        loggerMain.warn(`Console Run events: ${getErrorMessage(e)}`);
      }
    })
    .finally(() => {
      promiseEvents = undefined;
      if (!boolStopped && boolEventsRequested) requestConsoleEvents();
    });
}

function maintainConsoleEventDiagnostics(): void {
  try {
    const intDeleted = deleteExpiredConsoleEventDiagnostics();
    if (intDeleted) loggerMain.info(`Removed ${intDeleted} expired Run event diagnostics.`);
  } catch (e: unknown) {
    loggerMain.warn(`Run event diagnostic cleanup: ${getErrorMessage(e)}`);
  }
}

export function startConsoleEvents(): void {
  boolStopped = false;
  intEventRetryDelayMs = 2000;
  floatEventRetryAt = 0;
  strEventRetrySessionKey = undefined;
  boolEventFailureLogged = false;
  stopEventListener = onConsoleEventSaved(requestConsoleEvents);
  timerEventMaintenance = setInterval(
    maintainConsoleEventDiagnostics,
    INT_EVENT_MAINTENANCE_INTERVAL_MS,
  );
  requestConsoleEvents();
  maintainConsoleEventDiagnostics();
}

export async function stopConsoleEvents(): Promise<void> {
  const floatDeadline = performance.now() + INT_EVENT_SHUTDOWN_TIMEOUT_MS;
  boolStopped = true;
  stopEventListener?.();
  stopEventListener = undefined;
  clearTimeout(timerEventRetry);
  clearInterval(timerEventMaintenance);
  timerEventRetry = undefined;
  timerEventMaintenance = undefined;
  boolEventsRequested = false;
  await Promise.allSettled([promiseEvents]);

  const credential = getConsoleControlCredential();
  if (!credential) return;
  const strSessionKey = getConsoleWorkSessionKey(credential);
  if (strEventRetrySessionKey === strSessionKey && performance.now() < floatEventRetryAt)
    return;

  try {
    while (isCurrentConsoleControlCredential(credential)) {
      const floatRemainingMs = floatDeadline - performance.now();
      if (floatRemainingMs <= 0) return;
      if (
        !(await sendPendingConsoleEvents(
          strSessionKey,
          credential,
          Math.ceil(floatRemainingMs),
        ))
      )
        return;
    }
  } catch (e: unknown) {
    loggerMain.warn(`Console Run events during shutdown: ${getErrorMessage(e)}`);
  }
}
