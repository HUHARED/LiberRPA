// FileName: errors.ts

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

export function getFieldErrors(
  fields: Record<string, string[]> | undefined,
  path: string,
): string[] {
  return Object.entries(fields ?? {}).flatMap(([strField, arrMessage]) =>
    strField === path || strField.startsWith(`${path}.`) ? arrMessage : [],
  );
}
