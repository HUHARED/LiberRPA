// FileName: consoleClient.ts

import { isRecord } from "../../Common/typeCheck";
import {
  isEditorSessionInfo,
  type EditorSessionInfo,
} from "../../Domain/Console/consoleTypes";

export class ConsoleRequestError extends Error {
  public constructor(
    message: string,
    public readonly status: number,
    public readonly code: string = "",
  ) {
    super(message);
  }
}

export function normalizeConsoleUrl(value: string): string {
  let urlObj: URL;
  try {
    urlObj = new URL(value.trim());
  } catch {
    throw new Error("Enter a valid Console URL, including http:// or https://.");
  }
  if (
    !["http:", "https:"].includes(urlObj.protocol) ||
    urlObj.username !== "" ||
    urlObj.password !== "" ||
    urlObj.pathname !== "/" ||
    urlObj.search !== "" ||
    urlObj.hash !== ""
  ) {
    throw new Error(
      "Use a Console root URL without credentials, a path, query, or fragment.",
    );
  }
  return urlObj.origin;
}

export async function requestConsole(
  url: string,
  path: string,
  token?: string,
  body?: object,
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${url}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(token === undefined ? {} : { Authorization: `Bearer ${token}` }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      redirect: "manual",
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    throw new ConsoleRequestError(
      "Console could not be reached. Check its address and connection.",
      0,
    );
  }
  if (response.status >= 300 && response.status < 400) {
    throw new ConsoleRequestError(
      "Console redirects are not accepted. Use the final Console URL.",
      response.status,
    );
  }
  let responseValue: unknown;
  try {
    responseValue = await response.json();
  } catch {
    throw new ConsoleRequestError("Console returned an invalid response.", response.status);
  }
  if (!response.ok) {
    const errorValue = isRecord(responseValue) ? responseValue["error"] : undefined;
    const strMessage =
      isRecord(errorValue) && typeof errorValue["message"] === "string"
        ? errorValue["message"]
        : `Console request failed (${response.status}).`;
    const strCode =
      isRecord(errorValue) && typeof errorValue["code"] === "string"
        ? errorValue["code"]
        : "";
    throw new ConsoleRequestError(strMessage, response.status, strCode);
  }
  return responseValue;
}

export async function validateConsoleUrl(value: string): Promise<string> {
  const strUrl = normalizeConsoleUrl(value);
  const responseValue = await requestConsole(strUrl, "/api/clients/info/");
  if (
    !isRecord(responseValue) ||
    responseValue["product"] !== "LiberRPA Console" ||
    responseValue["protocol_version"] !== 1
  ) {
    throw new Error("This address does not provide a compatible LiberRPA Console.");
  }
  return strUrl;
}

export function parseEditorSession(value: unknown): EditorSessionInfo {
  if (!isEditorSessionInfo(value)) {
    throw new Error("Console returned invalid Editor session information.");
  }
  // Select known fields so a login token can never enter Webview state.
  return {
    session: value.session,
    user: value.user,
    organization: value.organization,
    is_org_admin: value.is_org_admin,
    account_departments: value.account_departments,
    computer: value.computer,
    version: value.version,
    last_seen_at: value.last_seen_at,
  };
}
