// FileName: useRetryDelay.ts

import { type ComputedRef, type Ref, computed, onBeforeUnmount, ref } from "vue";

export function useRetryDelay(): {
  intCurrentTimeMs: Ref<number>;
  intRetrySeconds: ComputedRef<number>;
  setRetryDelay: (seconds: number | null) => void;
} {
  const intCurrentTimeMs = ref(Date.now());
  const intRetryUntilMs = ref(0);
  const intRetrySeconds = computed(() =>
    Math.max(0, Math.ceil((intRetryUntilMs.value - intCurrentTimeMs.value) / 1000)),
  );
  const intIntervalHandle = setInterval(() => {
    intCurrentTimeMs.value = Date.now();
  }, 1000);
  onBeforeUnmount(() => clearInterval(intIntervalHandle));

  function setRetryDelay(seconds: number | null): void {
    if (seconds === null) return;

    intCurrentTimeMs.value = Date.now();
    intRetryUntilMs.value = intCurrentTimeMs.value + seconds * 1000;
  }

  return { intCurrentTimeMs, intRetrySeconds, setRetryDelay };
}
