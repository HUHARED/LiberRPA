// FileName: sessionStore.ts

import { defineStore } from "pinia";

import { getCurrentSession, getAccountAccess, signIn, signOut } from "../api/account";
import { setCsrfToken } from "../api/client";
import { ApiError, getApiError } from "../api/errors";

import type { AccountAccessResponse, SessionResponse } from "../api/generated/browserApi";

export type SessionStatus = "unknown" | "authenticated" | "anonymous";
type SessionNotice = "expired" | "signed_out" | null;

interface SessionState {
  session: Omit<SessionResponse, "csrf_token"> | null;
  access: AccountAccessResponse | null;
  status: SessionStatus;
  notice: SessionNotice;
  issue: ApiError | null;
  unavailable: boolean;
  busy: boolean;
  intRevision: number;
}

// Cache pending requests by $state so action proxies share one task without adding promises to reactive state.
const MAP_REFRESH_TASK = new WeakMap<object, Promise<void>>();

function announceSessionChange(): void {
  if (typeof window !== "undefined")
    window.dispatchEvent(new Event("console-session-changed"));
}

export const useSessionStore = defineStore("session", {
  state: (): SessionState => {
    return {
      session: null,
      access: null,
      status: "unknown",
      notice: null,
      issue: null,
      unavailable: false,
      busy: false,
      intRevision: 0,
    };
  },
  getters: {
    authenticated: (state): boolean => state.status === "authenticated",
  },
  actions: {
    clearSession(notice: SessionNotice = null): void {
      this.intRevision += 1;
      MAP_REFRESH_TASK.delete(this.$state);
      this.session = null;
      this.access = null;
      this.issue = null;
      this.unavailable = false;
      this.status = "anonymous";
      this.notice = notice;
      setCsrfToken(null);
    },

    applySession(currentSession: SessionResponse): void {
      if (this.session?.user.id !== currentSession.user.id) {
        // A different account must not inherit the previous account's mounted pages.
        if (this.status === "authenticated") this.status = "unknown";
        this.access = null;
      }
      this.session = {
        user: currentSession.user,
        expires_at: currentSession.expires_at,
      };
      setCsrfToken(currentSession.csrf_token);
    },

    refreshSession(): Promise<void> {
      const refreshTask = MAP_REFRESH_TASK.get(this.$state);
      if (refreshTask !== undefined) return refreshTask;
      const intCurrentRevision = this.intRevision;
      const pendingRefresh = (async () => {
        try {
          const currentSession = await getCurrentSession();
          if (intCurrentRevision !== this.intRevision) return;
          this.applySession(currentSession);
          const currentAccess = await getAccountAccess();
          if (intCurrentRevision !== this.intRevision) return;
          this.access = currentAccess;
          this.issue = null;
          this.unavailable = false;
          this.status = "authenticated";
          this.notice = null;
        } catch (e) {
          if (intCurrentRevision !== this.intRevision) return;
          const requestError = getApiError(e);
          if (
            requestError.statusCode === 401 &&
            requestError.code === "authentication_required"
          ) {
            this.clearSession(this.session === null ? null : "expired");
          } else if (
            requestError.code === "organization_access_required" &&
            this.session !== null
          ) {
            this.access = null;
            this.issue = requestError;
            this.unavailable = false;
            this.status = "authenticated";
          } else {
            // Availability is separate from the last confirmed authentication state.
            this.issue = requestError;
            this.unavailable = true;
          }
        }
      })().finally(() => {
        if (MAP_REFRESH_TASK.get(this.$state) === pendingRefresh)
          MAP_REFRESH_TASK.delete(this.$state);
      });
      MAP_REFRESH_TASK.set(this.$state, pendingRefresh);
      return pendingRefresh;
    },

    async initializeSession(): Promise<void> {
      if (this.status === "unknown") await this.refreshSession();
    },

    async signInAccount(
      email: string,
      password: string,
      rememberMe: boolean,
    ): Promise<void> {
      if (this.busy) throw new ApiError("A sign-in request is already in progress.");
      this.busy = true;
      this.intRevision += 1;
      MAP_REFRESH_TASK.delete(this.$state);
      const intCurrentRevision = this.intRevision;
      try {
        const currentSession = await signIn(email, password, rememberMe);
        if (intCurrentRevision !== this.intRevision) return;
        this.applySession(currentSession);
        announceSessionChange();
        // Verify that the browser accepted the session cookie before opening the workspace.
        await this.refreshSession();
      } finally {
        this.busy = false;
      }
    },

    async signOutAccount(): Promise<void> {
      if (this.busy) return;
      this.busy = true;
      // An earlier successful GET must never restore a session after this logout starts.
      this.intRevision += 1;
      MAP_REFRESH_TASK.delete(this.$state);
      try {
        await signOut();
        this.clearSession("signed_out");
        announceSessionChange();
      } finally {
        // A failed logout keeps the authenticated state and shows an explicit error to the user.
        this.busy = false;
      }
    },

    async refreshChangedSession(): Promise<void> {
      this.intRevision += 1;
      MAP_REFRESH_TASK.delete(this.$state);
      this.session = null;
      this.access = null;
      this.issue = null;
      this.unavailable = false;
      setCsrfToken(null);
      this.status = "unknown";
      await this.refreshSession();
    },
  },
});
