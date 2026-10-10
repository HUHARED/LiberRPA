// FileName: schedulerEngine.ts

import { randomUUID } from "crypto";
import { nextScheduleDate, parseScheduleCron } from "../../shared/cron";

import { getErrorMessage } from "../../shared/error";
import { RunSource, JobQueueState } from "../../shared/run";
import { INT_RETRY_DELAY_MS, RunConflictPolicy } from "../../shared/runOptions";
import { onRunFinished } from "../Run/lifecycle";
import { dictConfigExecutor } from "../Config/executorConfig";
import {
  dbSelectScheduleList,
  dbSelectScheduleRunDetail,
} from "../Database/scheduleRepository";
import { loggerMain } from "../Logging/logger";
import {
  getActiveJobQueueItems,
  hasActiveProjectRun,
  pythonRun,
} from "../Run/projectRunner";
import type { ProjectRunDetails, RunExecutionContext } from "../Run/types";
import type { JobQueueItem } from "../../shared/run";

type JobQueueChangedListener = (arrItem: JobQueueItem[]) => void;

type LocalJobQueueItem = Omit<
  JobQueueItem,
  "source" | "history_id" | "started_at_ms" | "estimated_run_at_ms"
> & { estimated_run_at_ms: number };

interface PendingRun {
  scheduleId: number;
  queueItem: LocalJobQueueItem;
  runConflictPolicy: RunConflictPolicy;
}

interface QueuedRun {
  queueItem: Omit<LocalJobQueueItem, "state">;
  runDetail: ProjectRunDetails;
  context?: RunExecutionContext;
}

const INT_SCHEDULER_CHECK_INTERVAL_MS = 1000;

const arrPendingRun: PendingRun[] = [];
const arrQueuedRun: QueuedRun[] = [];
const setJobQueueChangedListener = new Set<JobQueueChangedListener>();
let intLastPublishedWaitingCount = 0;

function isQueuedRunReady(queuedRun: QueuedRun, nowMs: number): boolean {
  return queuedRun.queueItem.estimated_run_at_ms <= nowMs;
}

function enqueueLocalRun(queuedRun: QueuedRun): void {
  arrQueuedRun.push(queuedRun);
  arrQueuedRun.sort(
    (left, right) =>
      left.queueItem.estimated_run_at_ms - right.queueItem.estimated_run_at_ms,
  );
}

onRunFinished((detail, context, fact) => {
  if (
    !boolSchedulerStarted ||
    context.source !== RunSource.Local ||
    !fact.retryEligible ||
    context.attempt > detail.retry_count
  )
    return;
  const intRetryAt = Date.now() + INT_RETRY_DELAY_MS;
  enqueueLocalRun({
    runDetail: structuredClone(detail),
    context: { ...context, attempt: context.attempt + 1 },
    queueItem: {
      queue_id: context.jobId,
      schedule_name: detail.schedule_name ?? "Manual Run",
      project_name: detail.name,
      project_version: detail.version,
      estimated_run_at_ms: intRetryAt,
    },
  });
  publishJobQueueChanged();
});

export function getLocalWaitingCount(): number {
  const intNowMs = Date.now();
  return arrQueuedRun.filter((queuedRun) => isQueuedRunReady(queuedRun, intNowMs)).length;
}

let timerSchedulerCheck: NodeJS.Timeout | undefined;
let promiseSchedulerTick: Promise<void> | undefined;
let boolSchedulerStarted = false;
let intPendingRunRevision = 0;

function requestSchedulerTick(): void {
  if (!boolSchedulerStarted) {
    return;
  }

  // Publish newly due retries even while another startup is still in progress.
  if (getLocalWaitingCount() !== intLastPublishedWaitingCount) {
    publishJobQueueChanged();
  }
  if (promiseSchedulerTick !== undefined) {
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
  arrQueuedRun.splice(0);
  arrPendingRun.splice(0);
  publishJobQueueChanged();
  loggerMain.info("Stop Scheduler engine.");
}

export function refreshSchedulerEngine(): void {
  resetPendingRuns();
  publishJobQueueChanged();
}

export function getJobQueueItems(): JobQueueItem[] {
  const intNowMs = Date.now();
  return [
    ...getActiveJobQueueItems(),
    ...arrQueuedRun.map((queuedRun) => ({
      ...queuedRun.queueItem,
      source: RunSource.Local,
      started_at_ms: null,
      history_id: null,
      state: isQueuedRunReady(queuedRun, intNowMs)
        ? JobQueueState.Waiting
        : JobQueueState.WaitingRetry,
    })),
    ...arrPendingRun.map(({ queueItem }) => ({
      ...queueItem,
      source: RunSource.Local,
      started_at_ms: null,
      history_id: null,
    })),
  ];
}

export function hasQueuedRunForProject(projectId: number): boolean {
  return arrQueuedRun.some(({ runDetail }) => runDetail.id === projectId);
}

export function cancelQueuedRun(queueId: string): void {
  const intIndex = arrQueuedRun.findIndex(
    ({ queueItem }) => queueItem.queue_id === queueId,
  );
  if (intIndex === -1) {
    loggerMain.debug(`Queued Run not found: ${queueId}`);
    return;
  }

  loggerMain.info(`Cancel queued Run: ${queueId}`);
  arrQueuedRun.splice(intIndex, 1);
  publishJobQueueChanged();
}

export function onJobQueueChanged(listener: JobQueueChangedListener): () => void {
  setJobQueueChangedListener.add(listener);
  return () => {
    setJobQueueChangedListener.delete(listener);
  };
}

function resetPendingRuns(): void {
  // Invalidate due candidates held by a Tick that is waiting for Python startup.
  intPendingRunRevision += 1;
  const intNowMs = Date.now();
  const arrSchedule = dbSelectScheduleList();
  const arrNextPending: PendingRun[] = [];

  for (const dictSchedule of arrSchedule) {
    if (!dictSchedule.enabled) {
      continue;
    }

    try {
      const intCurrentDateMs = Math.max(intNowMs, dictSchedule.period_start_ms - 1);
      const intervalObj = parseScheduleCron(
        dictSchedule.cron,
        dictConfigExecutor.timezone,
        {
          currentDate: new Date(intCurrentDateMs),
          endDate: new Date(dictSchedule.period_end_ms),
        },
      );
      const intEstimatedRunAtMs = nextScheduleDate(intervalObj).toDate().getTime();

      arrNextPending.push({
        scheduleId: dictSchedule.id,
        queueItem: {
          queue_id: `pending-${dictSchedule.id}-${intEstimatedRunAtMs}`,
          schedule_name: dictSchedule.name,
          project_name: dictSchedule.project_name,
          project_version: dictSchedule.project_version,
          estimated_run_at_ms: intEstimatedRunAtMs,
          state: JobQueueState.Pending,
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
  let boolOthersRunning = hasActiveProjectRun();

  const intReadyAtMs = Date.now();
  const intReadyIndex = arrQueuedRun.findIndex(
    (queuedRun) =>
      isQueuedRunReady(queuedRun, intReadyAtMs) &&
      (!boolOthersRunning ||
        (queuedRun.runDetail.run_conflict_policy ?? RunConflictPolicy.Concurrent) !==
          RunConflictPolicy.Wait),
  );
  if (intReadyIndex !== -1) {
    const queuedRun = arrQueuedRun.splice(intReadyIndex, 1)[0];
    publishJobQueueChanged();
    try {
      if (
        boolOthersRunning &&
        queuedRun.runDetail.run_conflict_policy === RunConflictPolicy.Skip
      ) {
        loggerMain.info("Skip local retry because another Run is active.");
      } else {
        await pythonRun(queuedRun.runDetail, queuedRun.context);
      }
      boolOthersRunning = hasActiveProjectRun();
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to start queued Run for '${queuedRun.queueItem.schedule_name}': ${getErrorMessage(e)}`,
      );
    }
  }

  if (!boolSchedulerStarted) {
    return;
  }

  const intNowMs = Date.now();
  const intRevision = intPendingRunRevision;
  const arrDueRun = arrPendingRun.filter(
    ({ queueItem }) => queueItem.estimated_run_at_ms <= intNowMs,
  );
  if (arrDueRun.length === 0) {
    return;
  }

  for (const dictDueRun of arrDueRun) {
    if (!boolSchedulerStarted || intRevision !== intPendingRunRevision) {
      return;
    }

    const { scheduleId, queueItem, runConflictPolicy } = dictDueRun;
    arrPendingRun.splice(arrPendingRun.indexOf(dictDueRun), 1);
    publishJobQueueChanged();
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
    if (!boolOthersRunning || runConflictPolicy === RunConflictPolicy.Concurrent) {
      try {
        await pythonRun(dictRunDetail);
        boolOthersRunning = hasActiveProjectRun();
      } catch (e: unknown) {
        loggerMain.error(
          `Failed to start scheduled Run for '${strScheduleName}': ${getErrorMessage(e)}`,
        );
      }
      continue;
    }

    if (runConflictPolicy === RunConflictPolicy.Wait) {
      loggerMain.info(`Move Schedule '${strScheduleName}' Run into the waiting queue.`);
      enqueueLocalRun({
        queueItem: {
          queue_id: randomUUID(),
          schedule_name: strScheduleName,
          project_name: dictRunDetail.name,
          project_version: dictRunDetail.version,
          estimated_run_at_ms: queueItem.estimated_run_at_ms,
        },
        runDetail: dictRunDetail,
      });
    } else {
      loggerMain.info(
        `Skip Schedule '${strScheduleName}' Run because another Run is active.`,
      );
    }
  }

  // The final startup await may also overlap a refresh or shutdown.
  if (!boolSchedulerStarted || intRevision !== intPendingRunRevision) {
    return;
  }

  resetPendingRuns();
  publishJobQueueChanged();
}

function publishJobQueueChanged(): void {
  const arrItem = getJobQueueItems();
  intLastPublishedWaitingCount = arrItem.filter(
    (item) => item.state === JobQueueState.Waiting,
  ).length;
  for (const listener of setJobQueueChangedListener) {
    try {
      listener(arrItem);
    } catch (e: unknown) {
      loggerMain.error(`Job Queue listener failed: ${getErrorMessage(e)}`);
    }
  }
}
