// FileName: sessionStore.ts

import { defineStore } from "pinia";

import { getCurrentSession, getAccountAccess, signIn, signOut } from "../api/account";
import { setCsrfToken } from "../api/client";
import { ApiError, getApiError } from "../api/errors";

import type {
  AccountAccessResponse,
  SessionUserResponse,
  SessionResponse,
} from "../api/generated/browserApi";

type SessionNotice =
  | "expired"
  | "signed_out"
  | "account_created"
  | "organization_created"
  | "password_changed"
  | "account_deleted"
  | null;

// Cache pending requests by $state so action proxies share one task without adding promises to reactive state.
const mapRefreshTask = new WeakMap<object, Promise<void>>();

function announceSessionChange(): void {
  if (typeof window !== "undefined")
    window.dispatchEvent(new Event("console-session-changed"));
}

export const useSessionStore = defineStore("session", {
  state: () => {
    return {
      session: null as Omit<SessionResponse, "csrf_token"> | null,
      access: null as AccountAccessResponse | null,
      status: "unknown" as "unknown" | "authenticated" | "anonymous",
      notice: null as SessionNotice,
      issue: null as ApiError | null,
      unavailable: false as boolean,
      busy: false as boolean,
      intRevision: 0 as number,
    };
  },
  getters: {
    authenticated: (state): boolean => state.status === "authenticated",
  },
  actions: {
    clearSession(notice: SessionNotice = null): void {
      this.intRevision += 1;
      mapRefreshTask.delete(this.$state);
      this.session = null;
      this.access = null;
      this.issue = null;
      this.unavailable = false;
      this.status = "anonymous";
      this.notice = notice;
      setCsrfToken(null);
    },

    finishAccountSignOut(notice: "password_changed" | "account_deleted"): void {
      this.clearSession(notice);
      announceSessionChange();
    },

    applyProfileUser(user: SessionUserResponse): void {
      if (this.session?.user.id !== user.id) return;

      // Ignore an older session read that could overwrite these newly saved profile fields.
      this.intRevision += 1;
      mapRefreshTask.delete(this.$state);
      this.session.user = user;
    },

    applyOrganizationName(organizationId: string, name: string): void {
      if (this.access?.organization.id !== organizationId) return;
      // Ignore an older access read that could restore the previous organization name.
      this.intRevision += 1;
      mapRefreshTask.delete(this.$state);
      this.access.organization.name = name;
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
      const refreshTask = mapRefreshTask.get(this.$state);
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
        if (mapRefreshTask.get(this.$state) === pendingRefresh)
          mapRefreshTask.delete(this.$state);
      });
      mapRefreshTask.set(this.$state, pendingRefresh);
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
      mapRefreshTask.delete(this.$state);
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
      mapRefreshTask.delete(this.$state);
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
      mapRefreshTask.delete(this.$state);
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
