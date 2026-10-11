// FileName: consoleTypes.ts
// IMPORTANT: Keep the Extension and Webview copies of this file synchronized.
// Synchronization is verified by scripts/checkSynchronizedFiles.mjs.
// - src/Domain/Console/consoleTypes.ts
// - webview-ui/src/Domain/Console/consoleTypes.ts

import { isRecord } from "../../Common/typeCheck";

export enum ConsoleConnection {
  SignedOut = "signedOut",
  Checking = "checking",
  Connected = "connected",
  Unavailable = "unavailable",
  Blocked = "blocked",
}

export enum ConsoleAction {
  SignIn = "signIn",
  SignOut = "signOut",
  ChangeAddress = "changeAddress",
  CheckConnection = "checkConnection",
}

export enum ConsoleDepartmentRole {
  Developer = "developer",
  Operator = "operator",
}

export interface ConsolePublishDepartment {
  id: string;
  name: string;
  path: string;
}

export function isConsolePublishDepartment(
  value: unknown,
): value is ConsolePublishDepartment {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["name"] === "string" &&
    typeof value["path"] === "string"
  );
}

export enum ConsolePublishStatus {
  NotRequested = "notRequested",
  Publishing = "publishing",
  Completed = "completed",
  Failed = "failed",
}

export interface ConsolePublishResult {
  status: ConsolePublishStatus;
  message: string;
  packageId: string | null;
}

export interface ConsoleDepartmentInfo {
  id: string;
  name: string;
  path: string;
  role: ConsoleDepartmentRole | null;
}

export interface EditorSessionInfo {
  session: { id: string; expires_at: string };
  user: { id: string; email: string; username: string };
  organization: { id: string; name: string };
  is_org_admin: boolean;
  account_departments: ConsoleDepartmentInfo[];
  computer_name: string;
  client_version: string;
  last_seen_at: string;
}

export interface ConsoleAccountState {
  url: string;
  rememberedEmail: string;
  connection: ConsoleConnection;
  signedIn: boolean;
  account: EditorSessionInfo | null;
  lastContactAt: string | null;
  message: string;
}

function isConsoleDepartment(value: unknown): value is ConsoleDepartmentInfo {
  return (
    isRecord(value) &&
    typeof value["id"] === "string" &&
    typeof value["name"] === "string" &&
    typeof value["path"] === "string" &&
    (value["role"] === null ||
      Object.values(ConsoleDepartmentRole).some((role) => role === value["role"]))
  );
}

export function isEditorSessionInfo(value: unknown): value is EditorSessionInfo {
  return (
    isRecord(value) &&
    isRecord(value["session"]) &&
    typeof value["session"]["id"] === "string" &&
    typeof value["session"]["expires_at"] === "string" &&
    isRecord(value["user"]) &&
    typeof value["user"]["id"] === "string" &&
    typeof value["user"]["email"] === "string" &&
    typeof value["user"]["username"] === "string" &&
    isRecord(value["organization"]) &&
    typeof value["organization"]["id"] === "string" &&
    typeof value["organization"]["name"] === "string" &&
    typeof value["is_org_admin"] === "boolean" &&
    Array.isArray(value["account_departments"]) &&
    value["account_departments"].every(isConsoleDepartment) &&
    typeof value["computer_name"] === "string" &&
    typeof value["client_version"] === "string" &&
    typeof value["last_seen_at"] === "string"
  );
}

export function isConsoleAccountState(value: unknown): value is ConsoleAccountState {
  return (
    isRecord(value) &&
    typeof value["url"] === "string" &&
    typeof value["rememberedEmail"] === "string" &&
    Object.values(ConsoleConnection).some(
      (connection) => connection === value["connection"],
    ) &&
    typeof value["signedIn"] === "boolean" &&
    (value["account"] === null || isEditorSessionInfo(value["account"])) &&
    (value["lastContactAt"] === null || typeof value["lastContactAt"] === "string") &&
    typeof value["message"] === "string"
  );
}
