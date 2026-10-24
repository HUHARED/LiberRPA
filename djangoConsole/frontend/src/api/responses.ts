// FileName: responses.ts

import { ApiError } from "./errors";

import type { MessageResponse } from "./generated/browserApi";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

export function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

export function isDateString(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

export function isNullableDateString(value: unknown): value is string | null {
  return value === null || isDateString(value);
}

export function rejectInvalidResponse(): never {
  throw new ApiError("The service returned an unexpected response. Please try again.", {
    code: "invalid_response",
  });
}

export function parseMessageResponse(payload: unknown): MessageResponse {
  if (!isRecord(payload) || typeof payload.message !== "string")
    return rejectInvalidResponse();
  return { message: payload.message };
}

export function parseResponseError(response: Response, payload: unknown): ApiError {
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
