// FileName: schedulerEngine.ts

import { CronExpressionParser } from "cron-parser";

import { dictConfigExecutor } from "./commonFunc";
import {
  dbSelectCountHistoryRunning,
  dbSelectSchedulerDetail,
  dbSelectSchedulerList,
} from "./database";
import { loggerMain } from "./logger";
import { pythonRun } from "./pythonFunc";
import { parseCustomProjectArgsJson } from "./validation";
import type {
  DictColumns_Project_Detail_Run,
  Dict_TaskQueue_ListItem,
} from "../shared/interface";

type WhenOthersRunning = "cancel" | "wait" | "run";

type RunQueueChangedListener = (arrItem: Dict_TaskQueue_ListItem[]) => void;

interface PendingRun {
  queueItem: Dict_TaskQueue_ListItem;
  whenOthersRunning: WhenOthersRunning;
}

const INT_SCHEDULER_CHECK_INTERVAL_MS = 1000;

const arrPendingRun: PendingRun[] = [];
const arrWaitingItem: Dict_TaskQueue_ListItem[] = [];
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
    void checkSchedulerQueue().catch((e: unknown) => {
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

export function getRunQueueItems(): Dict_TaskQueue_ListItem[] {
  return [
    ...arrWaitingItem.map((dictItem) => ({ ...dictItem })),
    ...arrPendingRun.map(({ queueItem }) => ({ ...queueItem })),
  ];
}

export function cancelWaitingRun(name: string, intEstimatedRunAtMs: number): void {
  const intIndex = arrWaitingItem.findIndex(
    (dictItem) =>
      dictItem.name === name && dictItem.estimated_run_at_ms === intEstimatedRunAtMs,
  );
  if (intIndex === -1) {
    loggerMain.debug(`Waiting Run not found: ${name}-${intEstimatedRunAtMs}`);
    return;
  }

  loggerMain.info(`Cancel waiting Run: ${name}-${intEstimatedRunAtMs}`);
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
  const arrScheduler = dbSelectSchedulerList();
  const arrNextPending: PendingRun[] = [];
  const setSchedulerName = new Set(arrScheduler.map((dictScheduler) => dictScheduler.name));

  for (let intIndex = arrWaitingItem.length - 1; intIndex >= 0; intIndex--) {
    if (!setSchedulerName.has(arrWaitingItem[intIndex].name)) {
      loggerMain.info(
        `Remove waiting Run because its Schedule no longer exists: ${arrWaitingItem[intIndex].name}`,
      );
      arrWaitingItem.splice(intIndex, 1);
    }
  }

  for (const dictScheduler of arrScheduler) {
    if (dictScheduler.enable !== 1) {
      continue;
    }

    try {
      const intCurrentDateMs = Math.max(intNowMs, dictScheduler.period_start_ms - 1);
      const intervalObj = CronExpressionParser.parse(dictScheduler.cron, {
        currentDate: new Date(intCurrentDateMs),
        endDate: new Date(dictScheduler.period_end_ms),
        tz: dictConfigExecutor.timezone,
      });

      arrNextPending.push({
        queueItem: {
          name: dictScheduler.name,
          project_source: dictScheduler.project_source,
          project_name: dictScheduler.project_name,
          project_version: dictScheduler.project_version,
          estimated_run_at_ms: intervalObj.next().toDate().getTime(),
          waiting: false,
        },
        whenOthersRunning: dictScheduler.when_others_running,
      });
    } catch (e: unknown) {
      loggerMain.debug(
        `No pending Run is available for Schedule '${dictScheduler.name}': ${
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

async function checkSchedulerQueue(): Promise<void> {
  if (boolIsChecking) {
    return;
  }

  boolIsChecking = true;
  try {
    let boolOthersRunning = dbSelectCountHistoryRunning();

    if (!boolOthersRunning && arrWaitingItem.length !== 0) {
      const dictWaitingItem = arrWaitingItem.shift();
      if (dictWaitingItem !== undefined) {
        publishRunQueueChanged();
        try {
          const boolStarted = await runSchedule(dictWaitingItem.name);
          if (boolStarted) {
            boolOthersRunning = dbSelectCountHistoryRunning();
          }
        } catch (e: unknown) {
          loggerMain.error(
            `Failed to start waiting Run for Schedule '${dictWaitingItem.name}': ${
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
        `Schedule '${queueItem.name}' reached its run time. when_others_running=${whenOthersRunning}`,
      );

      if (!boolOthersRunning || whenOthersRunning === "run") {
        try {
          const boolStarted = await runSchedule(queueItem.name);
          if (boolStarted) {
            boolOthersRunning = dbSelectCountHistoryRunning();
          }
        } catch (e: unknown) {
          loggerMain.error(
            `Failed to start scheduled Run for '${queueItem.name}': ${
              e instanceof Error ? e.message : String(e)
            }`,
          );
        }
        continue;
      }

      if (whenOthersRunning === "wait") {
        loggerMain.info(`Move Schedule '${queueItem.name}' Run into the waiting queue.`);
        arrWaitingItem.push({ ...queueItem, waiting: true });
      } else {
        loggerMain.info(
          `Skip Schedule '${queueItem.name}' Run because another Run is active.`,
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
  const dictDetail = dbSelectSchedulerDetail(name);
  if (dictDetail === undefined) {
    loggerMain.warn(`Schedule no longer exists: ${name}`);
    return false;
  }

  const dictRun: DictColumns_Project_Detail_Run = {
    scheduler_name: dictDetail.name,
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
