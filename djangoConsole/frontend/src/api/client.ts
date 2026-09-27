// FileName: client.ts

import { ApiError, buildResponseError, isRecord } from "./errors";

export interface ApiRequestOptions {
  method?: "GET" | "POST" | "PUT";
  body?: object;
  binaryBody?: Blob;
  chunkSha256?: string;
  responseType?: "json" | "blob";
  timeoutMs?: number;
}

const INT_REQUEST_TIMEOUT_MS = 15000;
let strCsrfToken: string | null = null;
let intCsrfRevision = 0;
let csrfRequest: Promise<string> | null = null;
let handleSessionInvalidated: (() => void) | null = null;

export function setSessionInvalidatedHandler(handler: (() => void) | null): void {
  handleSessionInvalidated = handler;
}

export function setCsrfToken(token: string | null): void {
  intCsrfRevision += 1;
  strCsrfToken = token;
  csrfRequest = null;
}

async function fetchJson(
  path: string,
  options: ApiRequestOptions,
  csrfToken?: string,
): Promise<unknown> {
  const intRequestRevision = intCsrfRevision;
  const abortController = new AbortController();
  const timeoutHandle = setTimeout(
    () => abortController.abort(),
    options.timeoutMs ?? INT_REQUEST_TIMEOUT_MS,
  );
  const requestHeaders = new Headers({ Accept: "application/json" });
  if (options.body !== undefined) requestHeaders.set("Content-Type", "application/json");
  if (options.binaryBody !== undefined)
    requestHeaders.set("Content-Type", "application/octet-stream");
  if (options.chunkSha256 !== undefined)
    requestHeaders.set("X-Chunk-SHA256", options.chunkSha256);
  if (csrfToken !== undefined) requestHeaders.set("X-CSRFToken", csrfToken);
  try {
    const response = await fetch(`/api${path}`, {
      method: options.method ?? "GET",
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      headers: requestHeaders,
      body:
        options.binaryBody ??
        (options.body === undefined ? undefined : JSON.stringify(options.body)),
      signal: abortController.signal,
    });
    let responsePayload: unknown = null;
    if (response.ok && options.responseType === "blob") {
      responsePayload = await response.blob();
    } else if (response.headers.get("Content-Type")?.includes("application/json")) {
      try {
        responsePayload = await response.json();
      } catch {
        // A malformed response must not become an authenticated session.
      }
    }
    if (!response.ok) {
      const apiError = buildResponseError(response, responsePayload);
      if (apiError.code === "csrf_failed" && intRequestRevision === intCsrfRevision)
        setCsrfToken(null);
      if (
        response.status === 401 &&
        apiError.code === "authentication_required" &&
        intRequestRevision === intCsrfRevision
      ) {
        handleSessionInvalidated?.();
      }
      throw apiError;
    }
    if (responsePayload === null) {
      throw new ApiError("The service returned an unexpected response. Please try again.", {
        statusCode: response.status,
        code: "invalid_response",
      });
    }
    return responsePayload;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(
      abortController.signal.aborted
        ? "The service took too long to respond. Please try again."
        : "Could not reach the service. Check your connection and try again.",
    );
  } finally {
    clearTimeout(timeoutHandle);
  }
}

async function getCsrfToken(): Promise<string> {
  if (strCsrfToken !== null) return strCsrfToken;
  if (csrfRequest !== null) return csrfRequest;
  const intRevision = intCsrfRevision;
  const pendingRequest = fetchJson("/auth/csrf/", {})
    .then((payload) => {
      if (
        !isRecord(payload) ||
        typeof payload.csrf_token !== "string" ||
        !payload.csrf_token
      ) {
        throw new ApiError("Could not prepare a secure request. Please try again.", {
          code: "invalid_response",
        });
      }
      if (intRevision !== intCsrfRevision) {
        if (strCsrfToken !== null) return strCsrfToken;
        throw new ApiError("Your session changed. Please try again.", {
          code: "session_changed",
        });
      }
      strCsrfToken = payload.csrf_token;
      return strCsrfToken;
    })
    .finally(() => {
      if (csrfRequest === pendingRequest) csrfRequest = null;
    });
  csrfRequest = pendingRequest;
  return pendingRequest;
}

export async function requestApi(
  path: string,
  options: ApiRequestOptions = {},
): Promise<unknown> {
  if (!path.startsWith("/") || path.startsWith("//") || /[\\\r\n]/.test(path)) {
    throw new Error("API paths must be relative to this Console instance.");
  }
  const strToken =
    options.method === "POST" || options.method === "PUT"
      ? await getCsrfToken()
      : undefined;
  // Do not replay mutations after a network or CSRF failure; the user keeps control of retries.
  return fetchJson(path, options, strToken);
}
