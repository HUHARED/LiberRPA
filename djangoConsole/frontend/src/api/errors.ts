// FileName: errors.ts

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export interface ApiErrorOptions {
  statusCode?: number;
  code?: string;
  fields?: Record<string, string[]>;
  retryAfterSeconds?: number | null;
  responsePayload?: unknown;
}

export class ApiError extends Error {
  readonly statusCode: number;
  readonly code: string;
  readonly fields: Record<string, string[]>;
  readonly retryAfterSeconds: number | null;
  readonly responsePayload: unknown;

  constructor(message: string, options: ApiErrorOptions = {}) {
    super(message);
    this.name = "ApiError";
    this.statusCode = options.statusCode ?? 0;
    this.code = options.code ?? "network_error";
    this.fields = options.fields ?? {};
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
    this.responsePayload = options.responsePayload;
  }
}

export function getApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError("The request could not be completed. Please try again.");
}

export function buildResponseError(response: Response, payload: unknown): ApiError {
  const dictErrorInfo = isRecord(payload) && isRecord(payload.error) ? payload.error : {};
  const dictFieldMessage: Record<string, string[]> = {};
  if (isRecord(dictErrorInfo.fields)) {
    for (const [strField, fieldMessage] of Object.entries(dictErrorInfo.fields)) {
      if (
        Array.isArray(fieldMessage) &&
        fieldMessage.every((message) => typeof message === "string")
      ) {
        dictFieldMessage[strField] = fieldMessage;
      }
    }
  }
  const strRetryAfter = response.headers.get("Retry-After");
  const intRetryAfter =
    strRetryAfter !== null && /^\d+$/.test(strRetryAfter)
      ? Math.min(Number(strRetryAfter), 86400)
      : null;
  const strFallback =
    response.status >= 500
      ? "The service is temporarily unavailable. Please try again."
      : response.status === 403
        ? "This request was not accepted. Refresh the page and try again."
        : "The request could not be completed. Please try again.";
  return new ApiError(
    typeof dictErrorInfo.message === "string" ? dictErrorInfo.message : strFallback,
    {
      statusCode: response.status,
      code: typeof dictErrorInfo.code === "string" ? dictErrorInfo.code : "request_failed",
      fields: dictFieldMessage,
      retryAfterSeconds: intRetryAfter,
      responsePayload: payload,
    },
  );
}
