// FileName: client.ts

import { isRecord, ApiError, buildResponseError } from "./errors";

export interface ApiRequestOptions {
  method?: "GET" | "POST" | "PUT";
  // JSON objects and arrays are serialized; Blob bodies are sent unchanged.
  body?: object;
  headers?: HeadersInit;
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
  return fetchApi(path, options, strToken);
}

async function getCsrfToken(): Promise<string> {
  if (strCsrfToken !== null) return strCsrfToken;
  if (csrfRequest !== null) return csrfRequest;
  const intRevision = intCsrfRevision;
  const pendingRequest = fetchApi("/auth/csrf/", {})
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

async function fetchApi(
  path: string,
  options: ApiRequestOptions,
  csrfToken?: string,
): Promise<unknown> {
  const intRequestRevision = intCsrfRevision;
  const requestHeaders = new Headers(options.headers);
  requestHeaders.set(
    "Accept",
    options.responseType === "blob"
      ? "application/octet-stream, application/json"
      : "application/json",
  );
  let requestBody: string | Blob | undefined;
  if (options.body instanceof Blob) {
    requestBody = options.body;
    requestHeaders.set("Content-Type", "application/octet-stream");
  } else if (options.body !== undefined) {
    requestBody = JSON.stringify(options.body);
    requestHeaders.set("Content-Type", "application/json");
  }
  if (csrfToken !== undefined) requestHeaders.set("X-CSRFToken", csrfToken);

  const abortController = new AbortController();
  const timeoutHandle = setTimeout(
    () => abortController.abort(),
    options.timeoutMs ?? INT_REQUEST_TIMEOUT_MS,
  );
  let response: Response;
  let responsePayload: unknown = null;
  try {
    response = await fetch(`/api${path}`, {
      method: options.method ?? "GET",
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      headers: requestHeaders,
      body: requestBody,
      signal: abortController.signal,
    });
    if (response.ok && options.responseType === "blob") {
      responsePayload = await response.blob();
    } else if (
      response.headers.get("Content-Type")?.split(";", 1)[0]?.trim().toLowerCase() ===
      "application/json"
    ) {
      try {
        responsePayload = await response.json();
      } catch (e) {
        // Only malformed JSON uses the response fallback; interrupted body reads remain transport failures.
        if (!(e instanceof SyntaxError)) throw e;
      }
    }
  } catch {
    throw new ApiError(
      abortController.signal.aborted
        ? "The service took too long to respond. Please try again."
        : "Could not complete the request. Check your connection and try again.",
      { code: abortController.signal.aborted ? "request_timeout" : "network_error" },
    );
  } finally {
    clearTimeout(timeoutHandle);
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
}
