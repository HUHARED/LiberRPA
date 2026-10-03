// FileName: sharedFiles.ts

import { requestApi } from "./client";
import { ApiError } from "./errors";
import { isRecord, isNonnegativeInteger } from "./responses";

import type {
  FileDeleteResponse,
  FileDownloadResponse,
  FileInfoResponse,
  FileListRequest,
  FileListResponse,
  FileUploadRequest,
  FileUploadResponse,
} from "./generated/browserApi";

const API_ROOT = "/shared-files/";
const UPLOAD_STATES = ["receiving", "completed", "failed", "expired", "canceled"];
const UUID_V4_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function rejectInvalidFileResponse(): never {
  throw new ApiError(
    "The service returned an unexpected response. Retry to check the same operation.",
    { code: "invalid_response" },
  );
}
function isFileInfoResponse(value: unknown): value is FileInfoResponse {
  return (
    isRecord(value) &&
    typeof value.path === "string" &&
    typeof value.name === "string" &&
    typeof value.department_path === "string" &&
    isNonnegativeInteger(value.size_bytes) &&
    typeof value.sha256 === "string" &&
    /^[0-9a-f]{64}$/.test(value.sha256) &&
    typeof value.uploaded_by_name === "string" &&
    typeof value.uploaded_at === "string"
  );
}
function parseFileUploadResponse(value: unknown): FileUploadResponse {
  if (
    !isRecord(value) ||
    typeof value.upload_id !== "string" ||
    !UUID_V4_PATTERN.test(value.upload_id) ||
    !UPLOAD_STATES.includes(String(value.state)) ||
    !isNonnegativeInteger(value.offset) ||
    !isNonnegativeInteger(value.size_bytes) ||
    value.offset > value.size_bytes ||
    !isNonnegativeInteger(value.chunk_bytes) ||
    value.chunk_bytes < 1 ||
    value.chunk_bytes > 4 * 1024 * 1024 ||
    typeof value.expires_at !== "string" ||
    !(value.file === null || isFileInfoResponse(value.file)) ||
    (value.state === "completed" && value.file === null)
  )
    return rejectInvalidFileResponse();
  return value as unknown as FileUploadResponse;
}
export async function getSha256(data: Blob | Uint8Array<ArrayBuffer>): Promise<string> {
  const bytes = data instanceof Blob ? await data.arrayBuffer() : data;
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
}
export async function getOrCreateFileRequestIdentity(
  userId: string,
  action: "upload" | "delete",
  body: object,
): Promise<{ key: string; requestId: string }> {
  const strDigest = await getSha256(new TextEncoder().encode(JSON.stringify(body)));
  const strKey = `file-request:${userId}:${action}:${strDigest}`;
  const strRequestId = sessionStorage.getItem(strKey) ?? crypto.randomUUID();
  sessionStorage.setItem(strKey, strRequestId);
  return { key: strKey, requestId: strRequestId };
}
export function clearFileRequestIdentity(identity: {
  key: string;
  requestId: string;
}): void {
  if (sessionStorage.getItem(identity.key) === identity.requestId)
    sessionStorage.removeItem(identity.key);
}
export async function getSharedFiles(body: FileListRequest): Promise<FileListResponse> {
  const value = await requestApi(`${API_ROOT}list/`, { method: "POST", body });
  if (
    !isRecord(value) ||
    !Array.isArray(value.files) ||
    !value.files.every(isFileInfoResponse) ||
    typeof value.department_path !== "string" ||
    !isRecord(value.usage) ||
    ![
      value.page,
      value.page_size,
      value.total_count,
      value.total_pages,
      value.usage.used_bytes,
      value.usage.reserved_bytes,
      value.usage.pending_cleanup_bytes,
      value.usage.limit_bytes,
      value.usage.max_file_bytes,
    ].every(isNonnegativeInteger) ||
    value.page === 0 ||
    value.total_pages === 0 ||
    value.page_size !== 50
  )
    return rejectInvalidFileResponse();
  return value as unknown as FileListResponse;
}
export async function createSharedUpload(
  body: FileUploadRequest,
): Promise<FileUploadResponse> {
  return parseFileUploadResponse(
    await requestApi(`${API_ROOT}uploads/`, { method: "POST", body }),
  );
}
export async function appendSharedChunk(
  uploadId: string,
  offset: number,
  chunk: Blob,
): Promise<FileUploadResponse> {
  return parseFileUploadResponse(
    await requestApi(
      `${API_ROOT}uploads/${encodeURIComponent(uploadId)}/chunks/${offset}/`,
      {
        method: "PUT",
        body: chunk,
        headers: { "X-Chunk-SHA256": await getSha256(chunk) },
        timeoutMs: 120000,
      },
    ),
  );
}
export async function finishSharedUpload(
  uploadId: string,
  action: "complete" | "cancel",
): Promise<FileUploadResponse> {
  return parseFileUploadResponse(
    await requestApi(`${API_ROOT}uploads/${encodeURIComponent(uploadId)}/${action}/`, {
      method: "POST",
      body: {},
      timeoutMs: 120000,
    }),
  );
}
export async function deleteSharedFiles(
  userId: string,
  paths: string[],
): Promise<FileDeleteResponse> {
  const body = { paths: [...paths].sort() };
  const identity = await getOrCreateFileRequestIdentity(userId, "delete", body);
  const result = await requestApi(`${API_ROOT}deletion/`, {
    method: "POST",
    body: { ...body, request_id: identity.requestId },
  });
  if (
    !isRecord(result) ||
    result.request_id !== identity.requestId ||
    !isNonnegativeInteger(result.deleted_count) ||
    !Array.isArray(result.deleted_paths) ||
    !result.deleted_paths.every((path) => typeof path === "string") ||
    !Array.isArray(result.missing_paths) ||
    !result.missing_paths.every((path) => typeof path === "string") ||
    result.deleted_count !== result.deleted_paths.length
  )
    return rejectInvalidFileResponse();
  clearFileRequestIdentity(identity);
  return result as unknown as FileDeleteResponse;
}
export async function downloadSharedFile(path: string): Promise<void> {
  const result = await requestApi(`${API_ROOT}downloads/`, {
    method: "POST",
    body: { path },
  });
  if (
    !isRecord(result) ||
    typeof result.transfer_id !== "string" ||
    !UUID_V4_PATTERN.test(result.transfer_id) ||
    typeof result.expires_at !== "string" ||
    !isFileInfoResponse(result.file)
  )
    return rejectInvalidFileResponse();
  const transfer = result as unknown as FileDownloadResponse;
  const fileBlob = await requestApi(
    `${API_ROOT}downloads/${encodeURIComponent(transfer.transfer_id)}/`,
    { responseType: "blob", timeoutMs: 300000 },
  );
  if (
    !(fileBlob instanceof Blob) ||
    fileBlob.size !== transfer.file.size_bytes ||
    (await getSha256(fileBlob)) !== transfer.file.sha256
  )
    throw new ApiError(
      "The downloaded file failed its integrity check. Download it again.",
    );
  const strUrl = URL.createObjectURL(fileBlob);
  const link = document.createElement("a");
  link.href = strUrl;
  link.download = transfer.file.name;
  document.body.append(link);
  link.click();
  link.remove();
  // Leave enough time for the browser to accept the save request.
  setTimeout(() => URL.revokeObjectURL(strUrl), 60000);
}
