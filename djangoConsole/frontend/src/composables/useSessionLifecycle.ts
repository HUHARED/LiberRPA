// FileName: useSessionLifecycle.ts

import { onBeforeUnmount, onMounted, watch } from "vue";
import { useEventListener, useWebSocket } from "@vueuse/core";

import { isRecord } from "../api/responses";
import { BrowserMessageType } from "../api/generated/browserApi";
import { useSessionStore } from "../stores/sessionStore";

const BROWSER_CLOSE_CODE = {
  NORMAL: 1000,
  GOING_AWAY: 1001,
  READY_TIMEOUT: 4000,
  INVALID_MESSAGE: 4002,
  SESSION_INVALID: 4401,
} as const;

const INT_READY_TIMEOUT_MS = 10000;
const INT_MAX_RETRY_MS = 30000;
const INT_FOCUS_THROTTLE_MS = 5000;
const STR_LOG_PREFIX = "[Browser WebSocket]";

export function useSessionLifecycle(): void {
  const sessionStore = useSessionStore();
  let broadcastChannel: BroadcastChannel | null = null;
  let strSocketUserId: string | undefined;
  let readyTimer: ReturnType<typeof setTimeout> | undefined;
  let intLastResumeAt = 0;
  let boolMounted = false;
  let boolPageActive = true;
  let boolInterrupted = false;
  let boolRefreshing = false;
  let boolRefreshRequested = false;
  let boolIdentityChanged = false;
  let boolRefreshNotifications = false;

  function announceNotifications(): void {
    window.dispatchEvent(new Event("console-notifications-changed"));
  }

  async function flushSessionRefresh(): Promise<void> {
    if (boolRefreshing || sessionStore.busy || !boolMounted) return;

    boolRefreshing = true;
    try {
      // A push received during an HTTP read must cause another read after it finishes.
      while (boolRefreshRequested && !sessionStore.busy && boolMounted) {
        boolRefreshRequested = false;
        const boolNotify = boolRefreshNotifications;
        boolRefreshNotifications = false;
        if (boolIdentityChanged) {
          boolIdentityChanged = false;
          stopSocket("Account changed in another tab.");
          await sessionStore.refreshChangedSession();
        } else {
          await sessionStore.refreshSession();
        }
        if (boolNotify && boolMounted && sessionStore.authenticated)
          announceNotifications();
      }
    } finally {
      boolRefreshing = false;
    }
  }

  function requestSessionRefresh(notifications = false): void {
    boolRefreshRequested = true;
    boolRefreshNotifications ||= notifications;
    void flushSessionRefresh();
  }

  function reportInterruption(message: string): void {
    if (!boolInterrupted) console.warn(`${STR_LOG_PREFIX} ${message}`);
    else console.debug(`${STR_LOG_PREFIX} ${message}`);
    boolInterrupted = true;
  }

  const strProtocol = location.protocol === "https:" ? "wss:" : "ws:";
  const {
    ws: socket,
    status,
    open,
    close,
  } = useWebSocket(`${strProtocol}//${location.host}/api/browser/events/`, {
    immediate: false,
    autoConnect: false,
    autoReconnect: {
      delay: (retries) => {
        const intDelay = Math.min(1000 * 2 ** (retries - 1), INT_MAX_RETRY_MS);
        console.debug(`${STR_LOG_PREFIX} Reconnecting in ${intDelay} ms.`);
        return intDelay;
      },
    },
    onDisconnected(currentSocket, event) {
      if (socket.value !== currentSocket) return;
      clearTimeout(readyTimer);
      const strMessage = `Disconnected: code=${event.code}.`;
      if (
        event.code === BROWSER_CLOSE_CODE.NORMAL ||
        event.code === BROWSER_CLOSE_CODE.GOING_AWAY ||
        event.code === BROWSER_CLOSE_CODE.SESSION_INVALID
      ) {
        console.info(`${STR_LOG_PREFIX} ${strMessage}`);
      } else {
        reportInterruption(strMessage);
      }
      // Only the HTTP session response decides whether to sign out; network loss does not.
      if (event.code === BROWSER_CLOSE_CODE.SESSION_INVALID) requestSessionRefresh();
    },
    onMessage(currentSocket, event: MessageEvent<unknown>) {
      let payload: unknown;
      try {
        payload = typeof event.data === "string" ? JSON.parse(event.data) : null;
      } catch {
        payload = null;
      }
      if (!isRecord(payload)) {
        currentSocket.close(BROWSER_CLOSE_CODE.INVALID_MESSAGE);
        return;
      }
      switch (payload.type) {
        case BrowserMessageType.Ready:
          clearTimeout(readyTimer);
          console.info(
            `${STR_LOG_PREFIX} ${boolInterrupted ? "Connection restored." : "Connected."}`,
          );
          boolInterrupted = false;
          // Reconcile changes made before connection or while the connection was down.
          requestSessionRefresh(true);
          break;
        case BrowserMessageType.SessionChanged:
          requestSessionRefresh();
          break;
        case BrowserMessageType.NotificationsChanged:
          announceNotifications();
          break;
        default:
          currentSocket.close(BROWSER_CLOSE_CODE.INVALID_MESSAGE);
      }
    },
  });

  // VueUse owns reconnection; this deadline also covers server-side session initialization.
  watch(
    socket,
    (currentSocket) => {
      clearTimeout(readyTimer);
      if (!currentSocket) return;
      readyTimer = setTimeout(() => {
        if (socket.value !== currentSocket) return;
        reportInterruption("Timed out waiting for the server to become ready.");
        currentSocket.close(BROWSER_CLOSE_CODE.READY_TIMEOUT);
      }, INT_READY_TIMEOUT_MS);
    },
    { flush: "sync" },
  );

  function stopSocket(reason: string): void {
    clearTimeout(readyTimer);
    if (socket.value && socket.value.readyState !== WebSocket.CLOSED)
      console.info(`${STR_LOG_PREFIX} Closing: ${reason}`);
    close();
    strSocketUserId = undefined;
  }

  function connectSocket(): void {
    if (
      !boolMounted ||
      !boolPageActive ||
      !navigator.onLine ||
      !sessionStore.authenticated ||
      sessionStore.busy ||
      socket.value !== undefined
    )
      return;

    strSocketUserId = sessionStore.session?.user.id;
    open();
  }

  function synchronizeConnection(): void {
    if (!boolMounted) return;
    if (!sessionStore.authenticated || strSocketUserId !== sessionStore.session?.user.id)
      stopSocket("Account session changed.");
    // A closed socket retained by VueUse is already waiting for its next retry.
    connectSocket();
    if (!sessionStore.busy) void flushSessionRefresh();
  }

  function resumeConnection(): void {
    if (document.visibilityState !== "visible" || !navigator.onLine) return;
    const intNow = Date.now();
    if (intNow - intLastResumeAt < INT_FOCUS_THROTTLE_MS) return;
    intLastResumeAt = intNow;

    if (status.value === "CLOSED") {
      stopSocket("Page resumed.");
      connectSocket();
    }
    // Anonymous tabs have no socket; focus also covers browsers without BroadcastChannel.
    if (!sessionStore.authenticated || sessionStore.unavailable) requestSessionRefresh();
  }

  function restoreNetwork(): void {
    // Discard a stale socket even if the browser has not reported its close yet.
    stopSocket("Network restored.");
    intLastResumeAt = 0;
    connectSocket();
    if (!sessionStore.authenticated || sessionStore.unavailable) requestSessionRefresh();
  }

  function suspendPage(): void {
    boolPageActive = false;
    stopSocket("Page closed or suspended.");
  }

  function resumePage(): void {
    boolPageActive = true;
    intLastResumeAt = 0;
    resumeConnection();
  }

  function announceChange(): void {
    // The message carries no credentials, account identifiers, or authorization state.
    broadcastChannel?.postMessage("changed");
  }

  watch(
    [
      () => sessionStore.status,
      () => sessionStore.session?.user.id,
      () => sessionStore.busy,
    ],
    synchronizeConnection,
  );

  useEventListener(window, "focus", resumeConnection);
  useEventListener(window, "pageshow", resumePage);
  useEventListener(window, "pagehide", suspendPage);
  useEventListener(window, "offline", () => {
    if (strSocketUserId) boolInterrupted = true;
    stopSocket("Network is offline.");
  });
  useEventListener(window, "online", restoreNetwork);
  useEventListener(document, "visibilitychange", resumeConnection);
  useEventListener(window, "console-session-changed", announceChange);

  onMounted(() => {
    boolMounted = true;
    if (typeof BroadcastChannel !== "undefined") {
      try {
        broadcastChannel = new BroadcastChannel("liberrpa-console-session");
        broadcastChannel.onmessage = (event: MessageEvent<unknown>) => {
          if (event.data !== "changed") return;
          boolIdentityChanged = true;
          requestSessionRefresh(true);
        };
      } catch {
        // Restricted browser storage still permits focus-based session checks.
      }
    }
    synchronizeConnection();
  });

  onBeforeUnmount(() => {
    boolMounted = false;
    stopSocket("Page unmounted.");
    broadcastChannel?.close();
  });
}
