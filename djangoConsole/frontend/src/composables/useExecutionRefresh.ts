// FileName: useExecutionRefresh.ts

import { type Ref, onBeforeUnmount, watch } from "vue";
import { useEventListener } from "@vueuse/core";

const STR_EXECUTION_CHANGE_EVENT = "console-execution-changed";
const INT_REFRESH_DELAY_MS = 100;

export function announceExecutionChange(jobId: string | null): void {
  window.dispatchEvent(new CustomEvent(STR_EXECUTION_CHANGE_EVENT, { detail: jobId }));
}

export function useExecutionRefresh(
  load: () => Promise<void>,
  busy: Ref<boolean>,
  retrySeconds: Ref<number>,
  matchesJob: (jobId: string) => boolean = () => true,
): { beginRefresh: () => boolean; requestRefresh: () => void } {
  let boolPending = false;
  let boolDisposed = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  function canRefresh(): boolean {
    return !boolDisposed && !document.hidden && !busy.value && retrySeconds.value === 0;
  }

  function scheduleRefresh(): void {
    if (!boolPending || timer !== undefined || !canRefresh()) return;
    timer = setTimeout(() => {
      timer = undefined;
      if (boolPending && canRefresh()) void load();
    }, INT_REFRESH_DELAY_MS);
  }

  function requestRefresh(): void {
    if (boolDisposed) return;
    boolPending = true;
    scheduleRefresh();
  }

  function beginRefresh(): boolean {
    if (boolDisposed) return false;
    if (!canRefresh()) {
      requestRefresh();
      return false;
    }
    // This read covers earlier hints; hints received while it is pending require another read.
    boolPending = false;
    clearTimeout(timer);
    timer = undefined;
    return true;
  }

  useEventListener(
    window,
    STR_EXECUTION_CHANGE_EVENT,
    (event: CustomEvent<string | null>) => {
      if (event.detail === null || matchesJob(event.detail)) requestRefresh();
    },
  );
  useEventListener(document, "visibilitychange", () => {
    if (!document.hidden) requestRefresh();
  });
  useEventListener(window, "pageshow", requestRefresh);
  watch([busy, retrySeconds], scheduleRefresh);

  onBeforeUnmount(() => {
    boolDisposed = true;
    clearTimeout(timer);
  });

  return { beginRefresh, requestRefresh };
}
