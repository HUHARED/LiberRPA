// FileName: error.ts

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function getErrorDetails(error: unknown): string {
  if (!(error instanceof Error)) {
    return String(error);
  }

  const strDetails = error.stack ?? `${error.name}: ${error.message}`;
  if (error.cause === undefined) {
    return strDetails;
  }

  return `${strDetails}
Caused by: ${getErrorDetails(error.cause)}`;
}
