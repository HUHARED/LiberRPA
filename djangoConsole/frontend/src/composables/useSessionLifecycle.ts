// FileName: useSessionLifecycle.ts

import { onBeforeUnmount, onMounted } from "vue";

import { useSessionStore } from "../stores/sessionStore";

const INT_SESSION_POLL_MS = 60000;
const INT_FOCUS_THROTTLE_MS = 5000;

export function useSessionLifecycle(): void {
  const sessionStore = useSessionStore();
  let broadcastChannel: BroadcastChannel | null = null;
  let intervalHandle: ReturnType<typeof setInterval> | undefined;
  let intLastRefreshAt = 0;

  function refreshVisibleSession(): void {
    if (document.visibilityState !== "visible" || sessionStore.busy) return;

    const intNow = Date.now();
    if (intNow - intLastRefreshAt < INT_FOCUS_THROTTLE_MS) return;
    intLastRefreshAt = intNow;
    void sessionStore.refreshSession();
  }

  function announceChange(): void {
    // The message carries no credentials, account identifiers, or authorization state.
    broadcastChannel?.postMessage("changed");
  }

  onMounted(() => {
    if (typeof BroadcastChannel !== "undefined") {
      try {
        broadcastChannel = new BroadcastChannel("liberrpa-console-session");
        broadcastChannel.onmessage = (event: MessageEvent<unknown>) => {
          if (event.data === "changed") void sessionStore.refreshChangedSession();
        };
      } catch {
        // Restricted browser storage still permits focus-based session checks.
      }
    }
    intervalHandle = setInterval(() => {
      if (sessionStore.status !== "anonymous") refreshVisibleSession();
    }, INT_SESSION_POLL_MS);
    window.addEventListener("focus", refreshVisibleSession);
    window.addEventListener("pageshow", refreshVisibleSession);
    window.addEventListener("online", refreshVisibleSession);
    document.addEventListener("visibilitychange", refreshVisibleSession);
    window.addEventListener("console-session-changed", announceChange);
  });
  onBeforeUnmount(() => {
    clearInterval(intervalHandle);
    broadcastChannel?.close();
    window.removeEventListener("focus", refreshVisibleSession);
    window.removeEventListener("pageshow", refreshVisibleSession);
    window.removeEventListener("online", refreshVisibleSession);
    document.removeEventListener("visibilitychange", refreshVisibleSession);
    window.removeEventListener("console-session-changed", announceChange);
  });
}
