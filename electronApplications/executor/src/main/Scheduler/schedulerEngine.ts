// FileName: schedulerEngine.ts

import { CronExpressionParser } from "cron-parser";

import { dictConfigExecutor } from "../Config/executorConfig";
import {
  dbSelectScheduleList,
  dbSelectScheduleRunDetail,
} from "../Database/scheduleRepository";
import { dbHasRunningRun } from "../Database/runHistoryRepository";
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

let intervalId: NodeJS.Timeout | undefined;
let boolIsChecking = false;

export function startSchedulerEngine(): void {
  if (intervalId !== undefined) {
    return;
  }

  loggerMain.info("Start Scheduler engine.");
  refreshSchedulerEngine();
  intervalId = setInterval(() => {
    void processSchedulerTick().catch((e: unknown) => {
      loggerMain.error(
        `Scheduler engine check failed: ${e instanceof Error ? e.message : String(e)}`,
      );
    });
  }, INT_SCHEDULER_CHECK_INTERVAL_MS);
}

export function stopSchedulerEngine(): void {
  if (intervalId === undefined) {
    return;
  }

  clearInterval(intervalId);
  intervalId = undefined;
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

export function cancelWaitingRun(scheduleName: string, estimatedRunAtMs: number): void {
  const intIndex = arrWaitingRun.findIndex(
    ({ queueItem }) =>
      queueItem.schedule_name === scheduleName &&
      queueItem.estimated_run_at_ms === estimatedRunAtMs,
  );
  if (intIndex === -1) {
    loggerMain.debug(`Waiting Run not found: ${scheduleName}-${estimatedRunAtMs}`);
    return;
  }

  loggerMain.info(`Cancel waiting Run: ${scheduleName}-${estimatedRunAtMs}`);
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

      arrNextPending.push({
        scheduleId: dictSchedule.id,
        queueItem: {
          schedule_name: dictSchedule.name,
          project_name: dictSchedule.project_name,
          project_version: dictSchedule.project_version,
          estimated_run_at_ms: intervalObj.next().toDate().getTime(),
          waiting: false,
        },
        runConflictPolicy: dictSchedule.run_conflict_policy,
      });
    } catch (e: unknown) {
      loggerMain.debug(
        `No pending Run is available for Schedule '${dictSchedule.name}': ${
          e instanceof Error ? e.message : String(e)
        }`,
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
  if (boolIsChecking) {
    return;
  }

  boolIsChecking = true;
  try {
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
            `Failed to start waiting Run for Schedule '${waitingRun.queueItem.schedule_name}': ${
              e instanceof Error ? e.message : String(e)
            }`,
          );
        }
      }
    }

    const intNowMs = Date.now();
    const arrDueRun = arrPendingRun.filter(
      ({ queueItem }) => queueItem.estimated_run_at_ms <= intNowMs,
    );
    if (arrDueRun.length === 0) {
      return;
    }

    for (const dictDueRun of arrDueRun) {
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
            `Failed to start scheduled Run for '${strScheduleName}': ${
              e instanceof Error ? e.message : String(e)
            }`,
          );
        }
        continue;
      }

      if (runConflictPolicy === "wait") {
        loggerMain.info(`Move Schedule '${strScheduleName}' Run into the waiting queue.`);
        arrWaitingRun.push({
          scheduleId,
          queueItem: {
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
  } finally {
    boolIsChecking = false;
  }
}

function publishRunQueueChanged(): void {
  const arrItem = getRunQueueItems();
  for (const listener of setListener_RunQueueChanged) {
    try {
      listener(arrItem);
    } catch (e: unknown) {
      loggerMain.error(
        `Run Queue listener failed: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  }
}
