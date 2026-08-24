import { CronExpressionParser } from "cron-parser";

import { dictConfigExecutor } from "../Config/config";
import {
  dbSelectScheduleDetail,
  dbSelectScheduleList,
} from "../Database/scheduleRepository";
import { dbHasRunningRun } from "../Database/runHistoryRepository";
import { loggerMain } from "../Logging/logger";
import { pythonRun } from "../Run/projectRunner";
import { parseCustomProjectArgsJson } from "../Common/validation";
import type { DictProjectRunDetail, DictRunQueueListItem } from "../../shared/run";

type WhenOthersRunning = "cancel" | "wait" | "run";

type RunQueueChangedListener = (arrItem: DictRunQueueListItem[]) => void;

interface PendingRun {
  queueItem: DictRunQueueListItem;
  whenOthersRunning: WhenOthersRunning;
}

const INT_SCHEDULER_CHECK_INTERVAL_MS = 1000;

const arrPendingRun: PendingRun[] = [];
const arrWaitingItem: DictRunQueueListItem[] = [];
const setRunQueueChangedListener = new Set<RunQueueChangedListener>();

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

export function getRunQueueItems(): DictRunQueueListItem[] {
  return [
    ...arrWaitingItem.map((dictItem) => ({ ...dictItem })),
    ...arrPendingRun.map(({ queueItem }) => ({ ...queueItem })),
  ];
}

export function cancelWaitingRun(scheduleName: string, intEstimatedRunAtMs: number): void {
  const intIndex = arrWaitingItem.findIndex(
    (dictItem) =>
      dictItem.schedule_name === scheduleName &&
      dictItem.estimated_run_at_ms === intEstimatedRunAtMs,
  );
  if (intIndex === -1) {
    loggerMain.debug(`Waiting Run not found: ${scheduleName}-${intEstimatedRunAtMs}`);
    return;
  }

  loggerMain.info(`Cancel waiting Run: ${scheduleName}-${intEstimatedRunAtMs}`);
  arrWaitingItem.splice(intIndex, 1);
  publishRunQueueChanged();
}

export function onRunQueueChanged(listener: RunQueueChangedListener): () => void {
  setRunQueueChangedListener.add(listener);
  return () => {
    setRunQueueChangedListener.delete(listener);
  };
}

function resetPendingRuns(): void {
  const intNowMs = Date.now();
  const arrSchedule = dbSelectScheduleList();
  const arrNextPending: PendingRun[] = [];
  const setScheduleName = new Set(arrSchedule.map((dictSchedule) => dictSchedule.name));

  for (let intIndex = arrWaitingItem.length - 1; intIndex >= 0; intIndex--) {
    if (!setScheduleName.has(arrWaitingItem[intIndex].schedule_name)) {
      loggerMain.info(
        `Remove waiting Run because its Schedule no longer exists: ${arrWaitingItem[intIndex].schedule_name}`,
      );
      arrWaitingItem.splice(intIndex, 1);
    }
  }

  for (const dictSchedule of arrSchedule) {
    if (dictSchedule.enable !== 1) {
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
        queueItem: {
          schedule_name: dictSchedule.name,
          project_source: dictSchedule.project_source,
          project_name: dictSchedule.project_name,
          project_version: dictSchedule.project_version,
          estimated_run_at_ms: intervalObj.next().toDate().getTime(),
          waiting: false,
        },
        whenOthersRunning: dictSchedule.when_others_running,
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
    let boolOthersRunning = dbHasRunningRun();

    if (!boolOthersRunning && arrWaitingItem.length !== 0) {
      const dictWaitingItem = arrWaitingItem.shift();
      if (dictWaitingItem !== undefined) {
        publishRunQueueChanged();
        try {
          const boolStarted = await runSchedule(dictWaitingItem.schedule_name);
          if (boolStarted) {
            boolOthersRunning = dbHasRunningRun();
          }
        } catch (e: unknown) {
          loggerMain.error(
            `Failed to start waiting Run for Schedule '${dictWaitingItem.schedule_name}': ${
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
      const { queueItem, whenOthersRunning } = dictDueRun;
      loggerMain.info(
        `Schedule '${queueItem.schedule_name}' reached its run time. when_others_running=${whenOthersRunning}`,
      );

      if (!boolOthersRunning || whenOthersRunning === "run") {
        try {
          const boolStarted = await runSchedule(queueItem.schedule_name);
          if (boolStarted) {
            boolOthersRunning = dbHasRunningRun();
          }
        } catch (e: unknown) {
          loggerMain.error(
            `Failed to start scheduled Run for '${queueItem.schedule_name}': ${
              e instanceof Error ? e.message : String(e)
            }`,
          );
        }
        continue;
      }

      if (whenOthersRunning === "wait") {
        loggerMain.info(
          `Move Schedule '${queueItem.schedule_name}' Run into the waiting queue.`,
        );
        arrWaitingItem.push({ ...queueItem, waiting: true });
      } else {
        loggerMain.info(
          `Skip Schedule '${queueItem.schedule_name}' Run because another Run is active.`,
        );
      }
    }

    resetPendingRuns();
    publishRunQueueChanged();
  } finally {
    boolIsChecking = false;
  }
}

async function runSchedule(name: string): Promise<boolean> {
  const dictDetail = dbSelectScheduleDetail(name);
  if (dictDetail === undefined) {
    loggerMain.warn(`Schedule no longer exists: ${name}`);
    return false;
  }

  const dictRun: DictProjectRunDetail = {
    schedule_name: dictDetail.name,
    project_source: dictDetail.project_source,
    id: dictDetail.project_id,
    name: dictDetail.project_name,
    version: dictDetail.project_version,
    python_environment_name: dictDetail.python_environment_name,
    timeout_min: dictDetail.timeout_min,
    builtin_log_level: dictDetail.builtin_log_level,
    builtin_record_video: dictDetail.builtin_record_video === 1,
    builtin_stop_shortcut: dictDetail.builtin_stop_shortcut === 1,
    builtin_highlight_ui: dictDetail.builtin_highlight_ui === 1,
    custom_prj_args: parseCustomProjectArgsJson(
      dictDetail.custom_prj_args,
      `Schedule '${dictDetail.name}' custom_prj_args`,
    ),
  };

  await pythonRun(dictRun);
  return true;
}

function publishRunQueueChanged(): void {
  const arrItem = getRunQueueItems();
  for (const listener of setRunQueueChangedListener) {
    try {
      listener(arrItem);
    } catch (e: unknown) {
      loggerMain.error(
        `Run Queue listener failed: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  }
}
