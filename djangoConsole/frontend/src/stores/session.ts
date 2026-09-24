// FileName: session.ts

import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";

import { getCurrentSession, getAccountAccess, signIn, signOut } from "../api/account";
import { setCsrfToken } from "../api/client";
import { ApiError, getApiError } from "../api/errors";

import type { AccountAccessResponse, SessionResponse } from "../api/generated/browserApi";

export type SessionStatus = "unknown" | "authenticated" | "anonymous" | "unavailable";
type SessionNotice = "expired" | "signed_out" | null;

function announceSessionChange(): void {
  if (typeof window !== "undefined")
    window.dispatchEvent(new Event("console-session-changed"));
}

export const useSessionStore = defineStore("session", () => {
  const sessionInfo = shallowRef<Omit<SessionResponse, "csrf_token"> | null>(null);
  const accessInfo = shallowRef<AccountAccessResponse | null>(null);
  const strStatus = ref<SessionStatus>("unknown");
  const strNotice = ref<SessionNotice>(null);
  const apiError = shallowRef<ApiError | null>(null);
  const boolBusy = ref(false);
  const boolAuthenticated = computed(() => strStatus.value === "authenticated");
  let intRevision = 0;
  let refreshTask: Promise<void> | null = null;

  function clearSession(notice: SessionNotice = null): void {
    intRevision += 1;
    refreshTask = null;
    sessionInfo.value = null;
    accessInfo.value = null;
    apiError.value = null;
    strStatus.value = "anonymous";
    strNotice.value = notice;
    setCsrfToken(null);
  }

  function applySession(currentSession: SessionResponse): void {
    if (sessionInfo.value?.user.id !== currentSession.user.id) accessInfo.value = null;
    sessionInfo.value = {
      user: currentSession.user,
      expires_at: currentSession.expires_at,
    };
    setCsrfToken(currentSession.csrf_token);
  }

  function refreshSession(): Promise<void> {
    if (refreshTask !== null) return refreshTask;
    const intCurrentRevision = intRevision;
    const pendingRefresh = (async () => {
      try {
        const currentSession = await getCurrentSession();
        if (intCurrentRevision !== intRevision) return;
        applySession(currentSession);
        const currentAccess = await getAccountAccess();
        if (intCurrentRevision !== intRevision) return;
        accessInfo.value = currentAccess;
        apiError.value = null;
        strStatus.value = "authenticated";
        strNotice.value = null;
      } catch (e) {
        if (intCurrentRevision !== intRevision) return;
        const requestError = getApiError(e);
        if (
          requestError.statusCode === 401 &&
          requestError.code === "authentication_required"
        ) {
          clearSession(sessionInfo.value === null ? null : "expired");
        } else if (
          requestError.code === "organization_access_required" &&
          sessionInfo.value !== null
        ) {
          accessInfo.value = null;
          apiError.value = requestError;
          strStatus.value = "authenticated";
        } else {
          // Transport failures retain the known identity while blocking unverified workspace actions.
          apiError.value = requestError;
          strStatus.value = "unavailable";
        }
      }
    })().finally(() => {
      if (refreshTask === pendingRefresh) refreshTask = null;
    });
    refreshTask = pendingRefresh;
    return pendingRefresh;
  }

  async function initializeSession(): Promise<void> {
    if (strStatus.value === "unknown") await refreshSession();
  }

  async function signInAccount(
    email: string,
    password: string,
    rememberMe: boolean,
  ): Promise<void> {
    if (boolBusy.value) throw new ApiError("A sign-in request is already in progress.");
    boolBusy.value = true;
    intRevision += 1;
    refreshTask = null;
    const intCurrentRevision = intRevision;
    try {
      const currentSession = await signIn(email, password, rememberMe);
      if (intCurrentRevision !== intRevision) return;
      applySession(currentSession);
      announceSessionChange();
      // Verify that the browser accepted the session cookie before opening the workspace.
      await refreshSession();
    } finally {
      boolBusy.value = false;
    }
  }

  async function signOutAccount(): Promise<void> {
    if (boolBusy.value) return;
    boolBusy.value = true;
    // An earlier successful GET must never restore a session after this logout starts.
    intRevision += 1;
    refreshTask = null;
    try {
      await signOut();
      clearSession("signed_out");
      announceSessionChange();
    } finally {
      // A failed logout keeps the authenticated state and shows an explicit error to the user.
      boolBusy.value = false;
    }
  }

  async function refreshChangedSession(): Promise<void> {
    intRevision += 1;
    refreshTask = null;
    sessionInfo.value = null;
    accessInfo.value = null;
    setCsrfToken(null);
    strStatus.value = "unknown";
    await refreshSession();
  }

  return {
    session: sessionInfo,
    access: accessInfo,
    status: strStatus,
    notice: strNotice,
    issue: apiError,
    busy: boolBusy,
    authenticated: boolAuthenticated,
    clearSession,
    refreshSession,
    initializeSession,
    signInAccount,
    signOutAccount,
    refreshChangedSession,
  };
});
