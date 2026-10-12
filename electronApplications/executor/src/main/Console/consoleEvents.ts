// FileName: consoleEvents.ts

import { getErrorMessage } from "../../shared/error";

import {
  ensureRecord,
  ensureString,
  ensureNonEmptyString,
  ensureBoolean,
} from "../Common/validation";
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
  type ConsoleEventRetentionResolution,
  onConsoleEventSaved,
  getPendingConsoleEvents,
  acknowledgeConsoleEvents,
  getConsoleEventRetentionCandidates,
  confirmConsoleEventRetention,
  pruneConsoleEventDiagnostics,
} from "./eventRepository";

const INT_EVENT_MAINTENANCE_INTERVAL_MS = 60 * 60 * 1000;
let timerEventRetry: NodeJS.Timeout | undefined;
let promiseEvents: Promise<void> | undefined;
let promiseEventMaintenance: Promise<void> | undefined;
let floatNextEventMaintenanceAt = 0;
let strEventMaintenanceSessionKey: string | undefined;
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
): Promise<boolean> {
  const arrEvent = getPendingConsoleEvents(strSessionKey);
  if (!arrEvent.length) return false;
  const response = await requestConsole(
    credential.consoleUrl,
    "executor/work/events/",
    credential.token,
    { events: arrEvent },
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

async function maintainConsoleEventDiagnostics(
  credential: ConsoleCredentialSnapshot | null,
): Promise<void> {
  const intDeleted = pruneConsoleEventDiagnostics();
  if (intDeleted) loggerMain.info(`Removed ${intDeleted} expired Run event diagnostics.`);
  if (!credential) return;
  const strSessionKey = getConsoleWorkSessionKey(credential);
  const arrCandidate = getConsoleEventRetentionCandidates(strSessionKey);
  if (!arrCandidate.length) return;
  const setAssignmentId = new Set(arrCandidate.map((entry) => entry.assignmentId));
  const response = await requestConsole(
    credential.consoleUrl,
    "executor/work/event-retention/",
    credential.token,
    { assignment_ids: [...setAssignmentId] },
  );
  if (boolStopped || !isCurrentConsoleControlCredential(credential)) return;
  if (!Array.isArray(response.resolved_assignments))
    throw new Error("Console returned invalid event retention information.");
  const setResolvedId = new Set<string>();
  const arrResolution: ConsoleEventRetentionResolution[] = [];
  for (const value of response.resolved_assignments) {
    const item = ensureRecord(value, "Resolved assignment");
    const strAssignmentId = ensureNonEmptyString(item.assignment_id, "Assignment ID");
    if (!setAssignmentId.has(strAssignmentId) || setResolvedId.has(strAssignmentId))
      throw new Error("Console returned an unexpected event retention identity.");
    const boolRunStarted = ensureBoolean(item.run_started, "Run started");
    setResolvedId.add(strAssignmentId);
    arrResolution.push({ assignmentId: strAssignmentId, runStarted: boolRunStarted });
  }
  confirmConsoleEventRetention(strSessionKey, arrCandidate, arrResolution);
}

function requestEventDiagnosticMaintenance(): void {
  if (boolStopped || promiseEventMaintenance) return;
  const credential = getConsoleControlCredential();
  const strSessionKey = credential ? getConsoleWorkSessionKey(credential) : undefined;
  if (
    performance.now() < floatNextEventMaintenanceAt &&
    strSessionKey === strEventMaintenanceSessionKey
  )
    return;
  strEventMaintenanceSessionKey = strSessionKey;
  floatNextEventMaintenanceAt = performance.now() + INT_EVENT_MAINTENANCE_INTERVAL_MS;
  // Independent of control and event delivery; no diagnostics means no extra HTTP request.
  promiseEventMaintenance = maintainConsoleEventDiagnostics(credential)
    .catch((e: unknown) => {
      loggerMain.warn(`Run event diagnostic cleanup: ${getErrorMessage(e)}`);
    })
    .finally(() => {
      promiseEventMaintenance = undefined;
    });
}

export function startConsoleEvents(): void {
  boolStopped = false;
  intEventRetryDelayMs = 2000;
  floatEventRetryAt = 0;
  strEventRetrySessionKey = undefined;
  boolEventFailureLogged = false;
  floatNextEventMaintenanceAt = 0;
  strEventMaintenanceSessionKey = undefined;
  stopEventListener = onConsoleEventSaved(requestConsoleEvents);
  timerEventMaintenance = setInterval(requestEventDiagnosticMaintenance, 2000);
  requestConsoleEvents();
  requestEventDiagnosticMaintenance();
}

export async function stopConsoleEvents(): Promise<void> {
  boolStopped = true;
  stopEventListener?.();
  stopEventListener = undefined;
  clearTimeout(timerEventRetry);
  clearInterval(timerEventMaintenance);
  timerEventRetry = undefined;
  timerEventMaintenance = undefined;
  boolEventsRequested = false;
  await Promise.allSettled([promiseEvents, promiseEventMaintenance]);
}
