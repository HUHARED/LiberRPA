// FileName: consoleAccount.ts

import { hostname } from "node:os";
import * as vscode from "vscode";

import { isRecord } from "../../Common/typeCheck";
import { getErrorMessage } from "../../Common/utils";
import {
  ConsoleConnection,
  type ConsoleAccountState,
  type EditorSessionInfo,
} from "../../Domain/Console/consoleTypes";
import {
  ConsoleRequestError,
  normalizeConsoleUrl,
  requestConsole,
  validateConsoleUrl,
  parseEditorSession,
} from "../../Adapter/Console/consoleClient";
import type { ConsoleCredentialSnapshot } from "../../Adapter/Console/consoleContextBridge";

const STR_ADDRESS_KEY = "console.url";
const STR_EMAIL_KEY = "console.email";
const STR_SESSION_KEY = "console.editorSession";

enum CredentialLoadResult {
  Unchanged = "unchanged",
  Changed = "changed",
  Unavailable = "unavailable",
}

interface ConsoleCredential {
  url: string;
  token: string;
}

export class ConsoleAccount implements vscode.Disposable {
  private readonly stateChanged = new vscode.EventEmitter<ConsoleAccountState>();
  public readonly onDidChangeState = this.stateChanged.event;
  private credential: ConsoleCredential | null = null;
  private disposed = false;
  private busy = false;
  private sessionRevision = 0;
  private pendingCredentialReload = false;
  private loadingCredential = false;
  private readonly secretSubscription: vscode.Disposable;
  private readonly credentialInitialization: Promise<CredentialLoadResult>;
  private readonly initialization: Promise<boolean>;
  private state: ConsoleAccountState;

  private getRememberedEmail(url: string): string {
    return url !== "" && url === this.context.globalState.get<string>(STR_ADDRESS_KEY, "")
      ? this.context.globalState.get<string>(STR_EMAIL_KEY, "")
      : "";
  }

  private publishState(): void {
    if (!this.disposed) {
      this.stateChanged.fire(this.state);
    }
  }

  private clearLocalSession(message: string): void {
    this.credential = null;
    this.state = {
      ...this.state,
      signedIn: false,
      connection: ConsoleConnection.SignedOut,
      account: null,
      lastContactAt: null,
      message,
    };
    this.publishState();
  }

  private async clearSession(message: string): Promise<void> {
    this.sessionRevision += 1;
    this.clearLocalSession(message);
    await this.context.secrets.delete(STR_SESSION_KEY);
  }

  private applySession(account: EditorSessionInfo): void {
    this.state = {
      ...this.state,
      signedIn: true,
      connection: ConsoleConnection.Connected,
      account,
      lastContactAt: new Date().toISOString(),
      message: "",
    };
    this.publishState();
  }

  private async handleConnectionError(error: unknown): Promise<void> {
    if (
      error instanceof ConsoleRequestError &&
      error.status === 401 &&
      error.code === "editor_authentication_required"
    ) {
      await this.clearSession("Your Console session is no longer valid. Sign in again.");
      return;
    }
    this.state = {
      ...this.state,
      connection:
        error instanceof ConsoleRequestError && error.status === 403
          ? ConsoleConnection.Blocked
          : ConsoleConnection.Unavailable,
      message: getErrorMessage(error),
    };
    this.publishState();
  }

  private async refreshSession(): Promise<void> {
    const credential = this.credential;
    if (credential === null) {
      return;
    }
    const intSessionRevision = this.sessionRevision;
    this.state = { ...this.state, connection: ConsoleConnection.Checking, message: "" };
    this.publishState();
    try {
      const responseValue = await requestConsole(
        credential.url,
        "/api/clients/editor/session/",
        credential.token,
      );
      if (intSessionRevision === this.sessionRevision) {
        this.applySession(parseEditorSession(responseValue));
      }
    } catch (e: unknown) {
      if (intSessionRevision === this.sessionRevision) {
        await this.handleConnectionError(e);
      }
    }
  }

  private handleSessionRestoreError(): void {
    this.pendingCredentialReload = true;
    this.clearLocalSession(
      "The saved Console session could not be read. Try again before changing accounts.",
    );
  }

  private async loadCredential(): Promise<CredentialLoadResult> {
    const intSessionRevision = this.sessionRevision;
    this.loadingCredential = true;
    this.publishState();
    try {
      const strCredential = await this.context.secrets.get(STR_SESSION_KEY);
      if (this.disposed || intSessionRevision !== this.sessionRevision) {
        return CredentialLoadResult.Unchanged;
      }
      if (strCredential === undefined) {
        const strUrl = this.context.globalState.get<string>(STR_ADDRESS_KEY, "");
        const strMessage =
          this.credential === null
            ? this.state.message
            : "Signed out in another Editor window.";
        this.state = {
          ...this.state,
          url: strUrl,
          rememberedEmail: this.getRememberedEmail(strUrl),
        };
        this.clearLocalSession(strMessage);
        return CredentialLoadResult.Unchanged;
      }
      const credentialValue: unknown = JSON.parse(strCredential);
      if (
        !isRecord(credentialValue) ||
        typeof credentialValue["url"] !== "string" ||
        typeof credentialValue["token"] !== "string" ||
        credentialValue["token"].length === 0
      ) {
        await this.clearSession("Sign in again to connect to Console.");
        return CredentialLoadResult.Unchanged;
      }
      const strUrl = normalizeConsoleUrl(credentialValue["url"]);
      const strRememberedEmail = this.getRememberedEmail(strUrl);
      if (
        this.credential?.token === credentialValue["token"] &&
        this.credential.url === strUrl
      ) {
        this.state = { ...this.state, rememberedEmail: strRememberedEmail };
        this.publishState();
        return CredentialLoadResult.Unchanged;
      }
      this.credential = { url: strUrl, token: credentialValue["token"] };
      this.state = {
        ...this.state,
        url: strUrl,
        rememberedEmail: strRememberedEmail,
        signedIn: true,
        account: null,
        lastContactAt: null,
        connection: ConsoleConnection.Checking,
      };
      return CredentialLoadResult.Changed;
    } catch {
      this.handleSessionRestoreError();
      return CredentialLoadResult.Unavailable;
    } finally {
      this.loadingCredential = false;
      this.publishState();
    }
  }

  private async restoreSession(
    credentialInitialization: Promise<CredentialLoadResult> = this.loadCredential(),
  ): Promise<boolean> {
    try {
      const result = await credentialInitialization;
      if (result === CredentialLoadResult.Unavailable) {
        return false;
      }
      if (result === CredentialLoadResult.Changed) {
        await this.refreshSession();
      }
      return true;
    } catch {
      this.handleSessionRestoreError();
      return false;
    }
  }

  private async reloadChangedCredential(): Promise<boolean> {
    while (this.pendingCredentialReload && !this.disposed) {
      this.pendingCredentialReload = false;
      if (!(await this.restoreSession())) {
        return false;
      }
    }
    return true;
  }

  private async runOperation(action?: () => Promise<void>): Promise<void> {
    await this.initialization;
    if (this.busy) {
      throw new Error("A Console request is already in progress. Try again shortly.");
    }
    this.busy = true;
    try {
      if (!(await this.reloadChangedCredential())) {
        throw new Error(this.state.message);
      }
      try {
        await action?.();
      } finally {
        await this.reloadChangedCredential();
      }
    } finally {
      this.busy = false;
    }
  }

  private async revokeSession(): Promise<void> {
    if (this.credential === null) {
      return;
    }
    const intSessionRevision = this.sessionRevision;
    try {
      await requestConsole(
        this.credential.url,
        "/api/clients/editor/logout/",
        this.credential.token,
        {},
      );
    } catch (e: unknown) {
      if (
        !(e instanceof ConsoleRequestError) ||
        e.status !== 401 ||
        e.code !== "editor_authentication_required"
      ) {
        throw e;
      }
    }
    if (intSessionRevision !== this.sessionRevision) {
      throw new Error("The Console session changed in another Editor window. Try again.");
    }
    await this.clearSession("");
  }

  public constructor(private readonly context: vscode.ExtensionContext) {
    const strUrl = context.globalState.get<string>(STR_ADDRESS_KEY, "");
    this.state = {
      url: strUrl,
      rememberedEmail: this.getRememberedEmail(strUrl),
      connection: ConsoleConnection.SignedOut,
      signedIn: false,
      account: null,
      lastContactAt: null,
      message: "",
    };
    this.credentialInitialization = this.loadCredential();
    this.initialization = this.restoreSession(this.credentialInitialization);
    this.secretSubscription = context.secrets.onDidChange((event) => {
      if (event.key !== STR_SESSION_KEY || this.disposed) {
        return;
      }
      this.sessionRevision += 1;
      this.pendingCredentialReload = true;
      this.publishState();
      void this.initialization
        .then(async () => {
          if (!this.busy && !this.disposed) {
            await this.runOperation();
          }
        })
        .catch(() => {
          // An account operation already in progress also reloads changed credentials.
        });
    });
  }

  public async getState(): Promise<ConsoleAccountState> {
    await this.initialization;
    return this.state;
  }

  public async waitForLocalCredential(): Promise<void> {
    await this.credentialInitialization;
  }

  public getPythonCredential(): ConsoleCredentialSnapshot | null {
    if (
      this.disposed ||
      this.loadingCredential ||
      this.pendingCredentialReload ||
      this.credential === null
    ) {
      return null;
    }
    // Keep this internal to the extension host; webviews receive account state only.
    return { consoleUrl: this.credential.url, token: this.credential.token };
  }

  public async changeAddress(value: string): Promise<void> {
    await this.runOperation(async () => {
      const intSessionRevision = this.sessionRevision;
      const strUrl = await validateConsoleUrl(value);
      if (intSessionRevision !== this.sessionRevision) {
        throw new Error("The Console session changed in another Editor window. Try again.");
      }
      if (strUrl === this.state.url) {
        return;
      }
      // Revoke the old session only after anonymous validation succeeds.
      await this.revokeSession();
      await this.context.globalState.update(STR_EMAIL_KEY, "");
      await this.context.globalState.update(STR_ADDRESS_KEY, strUrl);
      this.state = {
        ...this.state,
        url: strUrl,
        rememberedEmail: "",
        message: "Console address saved. Sign in to connect.",
      };
      this.publishState();
    });
  }

  public async signIn(email: string, password: string): Promise<void> {
    await this.runOperation(async () => {
      if (this.credential !== null) {
        throw new Error("Sign out before signing in with another account.");
      }
      const intSessionRevision = this.sessionRevision;
      const strUrl = await validateConsoleUrl(this.state.url);
      const manifestValue: unknown = this.context.extension.packageJSON;
      if (!isRecord(manifestValue) || typeof manifestValue["version"] !== "string") {
        throw new Error("The Editor extension version could not be read.");
      }
      const responseValue = await requestConsole(
        strUrl,
        "/api/clients/editor/login/",
        undefined,
        {
          email: email.trim(),
          password,
          computer: hostname(),
          version: manifestValue["version"],
        },
      );
      if (
        !isRecord(responseValue) ||
        typeof responseValue["token"] !== "string" ||
        responseValue["token"].length === 0
      ) {
        throw new Error("Console returned invalid login information.");
      }
      if (intSessionRevision !== this.sessionRevision) {
        await requestConsole(
          strUrl,
          "/api/clients/editor/logout/",
          responseValue["token"],
          {},
        );
        throw new Error("The Console session changed in another Editor window. Try again.");
      }
      const account = parseEditorSession(responseValue);
      const credential: ConsoleCredential = { url: strUrl, token: responseValue["token"] };
      try {
        await this.context.secrets.store(STR_SESSION_KEY, JSON.stringify(credential));
      } catch {
        await requestConsole(strUrl, "/api/clients/editor/logout/", credential.token, {});
        throw new Error("VS Code could not securely save the Console session.");
      }
      await this.context.globalState.update(STR_EMAIL_KEY, account.user.email);
      this.credential = credential;
      this.state = { ...this.state, rememberedEmail: account.user.email };
      this.applySession(account);
    });
  }

  public async signOut(): Promise<void> {
    await this.runOperation(async () => {
      await this.revokeSession();
    });
  }

  public async checkConnection(): Promise<void> {
    await this.runOperation(async () => {
      await this.refreshSession();
    });
  }

  public dispose(): void {
    this.disposed = true;
    this.secretSubscription.dispose();
    this.stateChanged.dispose();
  }
}
