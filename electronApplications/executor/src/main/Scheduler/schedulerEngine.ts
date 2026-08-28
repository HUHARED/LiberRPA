// FileName: schedulerEngine.ts

import { randomUUID } from "crypto";
import { CronExpressionParser } from "cron-parser";

import { getErrorMessage } from "../../shared/error";
import { dictConfigExecutor } from "../Config/executorConfig";
import { dbHasRunningRun } from "../Database/runHistoryRepository";
import {
  dbSelectScheduleList,
  dbSelectScheduleRunDetail,
} from "../Database/scheduleRepository";
import { loggerMain } from "../Logging/logger";
import { hasStartingRun, pythonRun } from "../Run/projectRunner";
import type { Dict_ProjectRun_Detail } from "../Run/types";
import type { Dict_ListItem_RunQueue } from "../../shared/run";
import type { Str_RunConflictPolicy } from "../../shared/schedule";

type Listener_RunQueueChanged = (arrItem: Dict_ListItem_RunQueue[]) => void;

interface PendingRun {
  scheduleId: number;
  queueItem: Dict_ListItem_RunQueue;
  runConflictPolicy: Str_RunConflictPolicy;
}

interface WaitingRun {
  scheduleId: number;
  queueItem: Dict_ListItem_RunQueue;
  runDetail: Dict_ProjectRun_Detail;
}

const INT_SCHEDULER_CHECK_INTERVAL_MS = 1000;

const arrPendingRun: PendingRun[] = [];
const arrWaitingRun: WaitingRun[] = [];
const setListener_RunQueueChanged = new Set<Listener_RunQueueChanged>();

let timerSchedulerCheck: NodeJS.Timeout | undefined;
let promiseSchedulerTick: Promise<void> | undefined;
let boolSchedulerStarted = false;

function requestSchedulerTick(): void {
  if (!boolSchedulerStarted || promiseSchedulerTick !== undefined) {
    return;
  }

  const promiseCurrentTick = processSchedulerTick().catch((e: unknown) => {
    loggerMain.error(`Scheduler engine check failed: ${getErrorMessage(e)}`);
  });
  promiseSchedulerTick = promiseCurrentTick;
  void promiseCurrentTick.finally(() => {
    if (promiseSchedulerTick === promiseCurrentTick) {
      promiseSchedulerTick = undefined;
    }
  });
}

export function startSchedulerEngine(): void {
  if (boolSchedulerStarted) {
    return;
  }

  loggerMain.info("Start Scheduler engine.");
  boolSchedulerStarted = true;
  refreshSchedulerEngine();
  timerSchedulerCheck = setInterval(requestSchedulerTick, INT_SCHEDULER_CHECK_INTERVAL_MS);
}

export async function stopSchedulerEngine(): Promise<void> {
  if (!boolSchedulerStarted && promiseSchedulerTick === undefined) {
    return;
  }

  boolSchedulerStarted = false;
  if (timerSchedulerCheck !== undefined) {
    clearInterval(timerSchedulerCheck);
    timerSchedulerCheck = undefined;
  }

  const promiseCurrentTick = promiseSchedulerTick;
  if (promiseCurrentTick !== undefined) {
    await promiseCurrentTick;
  }
  loggerMain.info("Stop Scheduler engine.");
}

export function refreshSchedulerEngine(): void {
  resetPendingRuns();
  publishRunQueueChanged();
}

export function getRunQueueItems(): Dict_ListItem_RunQueue[] {
  return [
    ...arrWaitingRun.map(({ queueItem }) => ({ ...queueItem })),
    ...arrPendingRun.map(({ queueItem }) => ({ ...queueItem })),
  ];
}

export function hasWaitingRunForProject(projectId: number): boolean {
  return arrWaitingRun.some(({ runDetail }) => runDetail.id === projectId);
}

export function cancelWaitingRun(queueId: string): void {
  const intIndex = arrWaitingRun.findIndex(
    ({ queueItem }) => queueItem.queue_id === queueId,
  );
  if (intIndex === -1) {
    loggerMain.debug(`Waiting Run not found: ${queueId}`);
    return;
  }

  const waitingRun = arrWaitingRun[intIndex];
  loggerMain.info(
    `Cancel waiting Run: ${waitingRun.queueItem.schedule_name}-${waitingRun.queueItem.estimated_run_at_ms}`,
  );
  arrWaitingRun.splice(intIndex, 1);
  publishRunQueueChanged();
}

export function onRunQueueChanged(listener: Listener_RunQueueChanged): () => void {
  setListener_RunQueueChanged.add(listener);
  return () => {
    setListener_RunQueueChanged.delete(listener);
  };
}

function resetPendingRuns(): void {
  const intNowMs = Date.now();
  const arrSchedule = dbSelectScheduleList();
  const arrNextPending: PendingRun[] = [];
  const setScheduleId = new Set(arrSchedule.map((dictSchedule) => dictSchedule.id));

  for (let intIndex = arrWaitingRun.length - 1; intIndex >= 0; intIndex--) {
    if (!setScheduleId.has(arrWaitingRun[intIndex].scheduleId)) {
      loggerMain.info(
        `Remove waiting Run because its Schedule no longer exists: ${arrWaitingRun[intIndex].queueItem.schedule_name}`,
      );
      arrWaitingRun.splice(intIndex, 1);
    }
  }

  for (const dictSchedule of arrSchedule) {
    if (!dictSchedule.enable) {
      continue;
    }

    try {
      const intCurrentDateMs = Math.max(intNowMs, dictSchedule.period_start_ms - 1);
      const intervalObj = CronExpressionParser.parse(dictSchedule.cron, {
        currentDate: new Date(intCurrentDateMs),
        endDate: new Date(dictSchedule.period_end_ms),
        tz: dictConfigExecutor.timezone,
      });
      const intEstimatedRunAtMs = intervalObj.next().toDate().getTime();

      arrNextPending.push({
        scheduleId: dictSchedule.id,
        queueItem: {
          queue_id: `pending-${dictSchedule.id}-${intEstimatedRunAtMs}`,
          schedule_name: dictSchedule.name,
          project_name: dictSchedule.project_name,
          project_version: dictSchedule.project_version,
          estimated_run_at_ms: intEstimatedRunAtMs,
          waiting: false,
        },
        runConflictPolicy: dictSchedule.run_conflict_policy,
      });
    } catch (e: unknown) {
      loggerMain.debug(
        `No pending Run is available for Schedule '${dictSchedule.name}': ${getErrorMessage(
          e,
        )}`,
      );
    }
  }

  arrNextPending.sort(
    (dictLeft, dictRight) =>
      dictLeft.queueItem.estimated_run_at_ms - dictRight.queueItem.estimated_run_at_ms,
  );
  arrPendingRun.splice(0, arrPendingRun.length, ...arrNextPending);
}

async function processSchedulerTick(): Promise<void> {
  let boolOthersRunning = dbHasRunningRun() || hasStartingRun();

  if (!boolOthersRunning && arrWaitingRun.length !== 0) {
    const waitingRun = arrWaitingRun.shift();
    if (waitingRun !== undefined) {
      publishRunQueueChanged();
      try {
        await pythonRun(waitingRun.runDetail);
        boolOthersRunning = dbHasRunningRun();
      } catch (e: unknown) {
        loggerMain.error(
          `Failed to start waiting Run for Schedule '${waitingRun.queueItem.schedule_name}': ${getErrorMessage(
            e,
          )}`,
        );
      }
    }
  }

  if (!boolSchedulerStarted) {
    return;
  }

  const intNowMs = Date.now();
  const arrDueRun = arrPendingRun.filter(
    ({ queueItem }) => queueItem.estimated_run_at_ms <= intNowMs,
  );
  if (arrDueRun.length === 0) {
    return;
  }

  for (const dictDueRun of arrDueRun) {
    if (!boolSchedulerStarted) {
      return;
    }

    const { scheduleId, queueItem, runConflictPolicy } = dictDueRun;
    loggerMain.info(
      `Schedule '${queueItem.schedule_name}' reached its run time. run_conflict_policy=${runConflictPolicy}`,
    );

    const dictRunDetail = dbSelectScheduleRunDetail(scheduleId);
    if (dictRunDetail === undefined) {
      loggerMain.warn(
        `Schedule no longer exists: ${queueItem.schedule_name} (ID ${scheduleId})`,
      );
      continue;
    }

    const strScheduleName = dictRunDetail.schedule_name ?? queueItem.schedule_name;
    if (!boolOthersRunning || runConflictPolicy === "concurrent") {
      try {
        await pythonRun(dictRunDetail);
        boolOthersRunning = dbHasRunningRun();
      } catch (e: unknown) {
        loggerMain.error(
          `Failed to start scheduled Run for '${strScheduleName}': ${getErrorMessage(e)}`,
        );
      }
      continue;
    }

    if (runConflictPolicy === "wait") {
      loggerMain.info(`Move Schedule '${strScheduleName}' Run into the waiting queue.`);
      arrWaitingRun.push({
        scheduleId,
        queueItem: {
          queue_id: randomUUID(),
          schedule_name: strScheduleName,
          project_name: dictRunDetail.name,
          project_version: dictRunDetail.version,
          estimated_run_at_ms: queueItem.estimated_run_at_ms,
          waiting: true,
        },
        runDetail: dictRunDetail,
      });
    } else {
      loggerMain.info(
        `Skip Schedule '${strScheduleName}' Run because another Run is active.`,
      );
    }
  }

  resetPendingRuns();
  publishRunQueueChanged();
}

function publishRunQueueChanged(): void {
  const arrItem = getRunQueueItems();
  for (const listener of setListener_RunQueueChanged) {
    try {
      listener(arrItem);
    } catch (e: unknown) {
      loggerMain.error(`Run Queue listener failed: ${getErrorMessage(e)}`);
    }
  }
}
