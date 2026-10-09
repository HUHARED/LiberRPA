// FileName: consoleApi.ts

import {
  ConsoleDepartmentRole,
  type ConsoleSessionInfo,
  type ConsoleExecutorPage,
} from "../../shared/consoleAccount";
import {
  ensureRecord,
  ensureString,
  ensureNonEmptyString,
  ensureBoolean,
  ensurePositiveInteger,
} from "../Common/validation";

export class ConsoleRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly retryAfterMs = 0,
  ) {
    super(message);
  }
}

export function normalizeConsoleUrl(consoleUrl: string): string {
  let urlObj: URL;
  try {
    urlObj = new URL(consoleUrl.trim());
  } catch {
    throw new Error("Enter a valid Console URL, including http:// or https://.");
  }
  if (
    !["http:", "https:"].includes(urlObj.protocol) ||
    urlObj.username ||
    urlObj.password ||
    urlObj.search ||
    urlObj.hash ||
    urlObj.pathname !== "/"
  ) {
    throw new Error(
      "Use an HTTP or HTTPS root URL without credentials, a path, a query, or a fragment.",
    );
  }
  return urlObj.origin;
}

export async function requestConsole(
  consoleUrl: string,
  route: string,
  token = "",
  body?: object,
): Promise<Record<string, unknown>> {
  let response: Response;
  try {
    response = await fetch(`${consoleUrl}/api/clients/${route}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(token === "" ? {} : { Authorization: `Bearer ${token}` }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      redirect: "error",
      credentials: "omit",
      signal: AbortSignal.timeout(10000),
    });
  } catch {
    throw new Error(
      "Cannot reach Console. Check the address and connection, then retry. Redirects are not accepted.",
    );
  }
  let dictResponse: Record<string, unknown> = {};
  let strErrorMessage = `Console request failed (HTTP ${response.status}).`;
  let strErrorCode = "http_error";
  try {
    dictResponse = ensureRecord(await response.json(), "Console response");
    if (!response.ok) {
      const dictError = ensureRecord(dictResponse.error, "Console error");
      strErrorMessage = ensureString(dictError.message, "Console error.message");
      strErrorCode = ensureString(dictError.code, "Console error.code");
    }
  } catch {
    if (response.ok) throw new Error("Console returned an invalid response.");
    // Preserve HTTP status and retry timing even when a proxy returns a non-JSON error.
  }
  if (!response.ok) {
    const strRetryAfter = response.headers.get("Retry-After")?.trim() ?? "";
    const intRetryAfterMs = /^\d+$/.test(strRetryAfter)
      ? Number(strRetryAfter) * 1000
      : Math.max(0, Date.parse(strRetryAfter) - Date.now());
    throw new ConsoleRequestError(
      strErrorMessage,
      response.status,
      strErrorCode,
      Number.isFinite(intRetryAfterMs) ? intRetryAfterMs : 0,
    );
  }
  return dictResponse;
}

function parseIdentity(value: Record<string, unknown>): { id: string; name: string } {
  return {
    id: ensureNonEmptyString(value.id, "Console identity.id"),
    name: ensureString(value.name, "Console identity.name"),
  };
}

function parseDepartment(value: Record<string, unknown>): {
  id: string;
  name: string;
  path: string;
} {
  return {
    ...parseIdentity(value),
    path: ensureString(value.path, "Console department.path"),
  };
}

export function parseConsoleSession(response: Record<string, unknown>): ConsoleSessionInfo {
  const dictSession = ensureRecord(response.session, "Console session");
  const dictUser = ensureRecord(response.user, "Console user");
  const boolSelectionRequired = ensureBoolean(
    dictSession.selection_required,
    "Console session.selection_required",
  );
  const dictExecutor =
    response.executor === null ? null : ensureRecord(response.executor, "Console executor");
  if (boolSelectionRequired !== (dictExecutor === null)) {
    throw new Error("Console returned an inconsistent Executor association.");
  }
  if (!Array.isArray(response.account_departments)) {
    throw new Error("Console returned invalid account departments.");
  }
  return {
    session: {
      id: ensureNonEmptyString(dictSession.id, "Console session.id"),
      selection_required: boolSelectionRequired,
      expires_at: ensureString(dictSession.expires_at, "Console session.expires_at"),
    },
    user: {
      id: ensureNonEmptyString(dictUser.id, "Console user.id"),
      email: ensureString(dictUser.email, "Console user.email"),
      username: ensureString(dictUser.username, "Console user.username"),
    },
    organization: parseIdentity(
      ensureRecord(response.organization, "Console organization"),
    ),
    is_org_admin: ensureBoolean(response.is_org_admin, "Console is_org_admin"),
    account_departments: response.account_departments.map((departmentValue) => {
      const dictDepartment = ensureRecord(departmentValue, "Console department");
      const role = dictDepartment.role;
      if (
        role !== null &&
        role !== ConsoleDepartmentRole.Developer &&
        role !== ConsoleDepartmentRole.Operator
      ) {
        throw new Error("Console returned an invalid department role.");
      }
      return {
        ...parseDepartment(dictDepartment),
        role,
      };
    }),
    executor:
      dictExecutor === null
        ? null
        : {
            ...parseIdentity(dictExecutor),
            department_id: ensureString(
              dictExecutor.department_id,
              "Executor department_id",
            ),
            dispatch_enabled: ensureBoolean(
              dictExecutor.dispatch_enabled,
              "Executor dispatch_enabled",
            ),
          },
    last_seen_at:
      response.last_seen_at === null
        ? null
        : ensureString(response.last_seen_at, "Console last_seen_at"),
    heartbeat_interval_seconds: ensurePositiveInteger(
      response.heartbeat_interval_seconds,
      "Console heartbeat_interval_seconds",
    ),
  };
}

export function parseConsoleHeartbeat(
  response: Record<string, unknown>,
  currentSession: ConsoleSessionInfo | null,
): ConsoleSessionInfo {
  if (currentSession?.executor == null) {
    throw new Error("Console returned a heartbeat without an Executor association.");
  }
  const strSessionId = ensureNonEmptyString(response.session_id, "Console session_id");
  const strExecutorId = ensureNonEmptyString(response.executor_id, "Console executor_id");
  const account =
    response.account === null
      ? currentSession
      : parseConsoleSession(ensureRecord(response.account, "Console account"));
  if (
    strSessionId !== currentSession.session.id ||
    strExecutorId !== currentSession.executor.id ||
    account.session.id !== strSessionId ||
    account.executor?.id !== strExecutorId ||
    account.user.id !== currentSession.user.id ||
    account.organization.id !== currentSession.organization.id
  ) {
    throw new Error("Console returned a heartbeat for a different Executor association.");
  }
  return {
    ...account,
    session: {
      ...account.session,
      expires_at: ensureString(response.expires_at, "Console expires_at"),
    },
    executor: {
      ...account.executor,
      dispatch_enabled: ensureBoolean(
        response.dispatch_enabled,
        "Console dispatch_enabled",
      ),
    },
    last_seen_at: ensureString(response.last_seen_at, "Console last_seen_at"),
  };
}

export function parseExecutorChoices(
  response: Record<string, unknown>,
): ConsoleExecutorPage {
  if (!Array.isArray(response.executors)) {
    throw new Error("Console returned an invalid Executor list.");
  }
  return {
    executors: response.executors.map((executorValue) => {
      const dictExecutor = ensureRecord(executorValue, "Console Executor choice");
      return {
        ...parseIdentity(dictExecutor),
        department: parseDepartment(
          ensureRecord(dictExecutor.department, "Console department"),
        ),
        dispatch_enabled: ensureBoolean(
          dictExecutor.dispatch_enabled,
          "Executor dispatch_enabled",
        ),
      };
    }),
    page: ensurePositiveInteger(response.page, "Console page"),
    total_pages: ensurePositiveInteger(response.total_pages, "Console total_pages"),
  };
}
