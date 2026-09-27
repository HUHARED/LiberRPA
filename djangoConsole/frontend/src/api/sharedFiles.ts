// FileName: sharedFiles.ts

import { requestApi } from "./client";
import { ApiError, isRecord } from "./errors";
import type {
  FileDeleteResponse,
  FileDownloadResponse,
  FileInfoResponse,
  FileListRequest,
  FileListResponse,
  FileUploadRequest,
  FileUploadResponse,
} from "./generated/browserApi";

const ROOT = "/shared-files/";
const UPLOAD_STATES = ["receiving", "completed", "failed", "expired", "canceled"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function invalidResponse(): never {
  throw new ApiError(
    "The service returned an unexpected response. Retry to check the same operation.",
    { code: "invalid_response" },
  );
}
const isCount = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
function isFile(value: unknown): value is FileInfoResponse {
  return (
    isRecord(value) &&
    typeof value.path === "string" &&
    typeof value.name === "string" &&
    typeof value.department_path === "string" &&
    isCount(value.size_bytes) &&
    typeof value.sha256 === "string" &&
    /^[0-9a-f]{64}$/.test(value.sha256) &&
    typeof value.uploaded_by_name === "string" &&
    typeof value.uploaded_at === "string"
  );
}
function uploadResult(value: unknown): FileUploadResponse {
  if (
    !isRecord(value) ||
    typeof value.upload_id !== "string" ||
    !UUID.test(value.upload_id) ||
    !UPLOAD_STATES.includes(String(value.state)) ||
    !isCount(value.offset) ||
    !isCount(value.size_bytes) ||
    value.offset > value.size_bytes ||
    !isCount(value.chunk_bytes) ||
    value.chunk_bytes < 1 ||
    value.chunk_bytes > 4 * 1024 * 1024 ||
    typeof value.expires_at !== "string" ||
    !(value.file === null || isFile(value.file)) ||
    (value.state === "completed" && value.file === null)
  )
    return invalidResponse();
  return value as unknown as FileUploadResponse;
}
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GiB`;
}
export async function sha256(data: Blob | Uint8Array<ArrayBuffer>): Promise<string> {
  const bytes = data instanceof Blob ? await data.arrayBuffer() : data;
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
}
export async function fileRequestIdentity(
  userId: string,
  action: "upload" | "delete",
  body: object,
): Promise<{ key: string; requestId: string }> {
  const digest = await sha256(new TextEncoder().encode(JSON.stringify(body)));
  const key = `file-request:${userId}:${action}:${digest}`;
  const requestId = sessionStorage.getItem(key) ?? crypto.randomUUID();
  sessionStorage.setItem(key, requestId);
  return { key, requestId };
}
export function finishFileRequest(identity: { key: string; requestId: string }): void {
  if (sessionStorage.getItem(identity.key) === identity.requestId)
    sessionStorage.removeItem(identity.key);
}
export async function getSharedFiles(body: FileListRequest): Promise<FileListResponse> {
  const value = await requestApi(`${ROOT}list/`, { method: "POST", body });
  if (
    !isRecord(value) ||
    !Array.isArray(value.files) ||
    !value.files.every(isFile) ||
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
    ].every(isCount) ||
    value.page === 0 ||
    value.total_pages === 0 ||
    value.page_size !== 100
  )
    return invalidResponse();
  return value as unknown as FileListResponse;
}
export async function createSharedUpload(
  body: FileUploadRequest,
): Promise<FileUploadResponse> {
  return uploadResult(await requestApi(`${ROOT}uploads/`, { method: "POST", body }));
}
export async function appendSharedChunk(
  id: string,
  offset: number,
  data: Blob,
): Promise<FileUploadResponse> {
  return uploadResult(
    await requestApi(`${ROOT}uploads/${encodeURIComponent(id)}/chunks/${offset}/`, {
      method: "PUT",
      binaryBody: data,
      chunkSha256: await sha256(data),
      timeoutMs: 120000,
    }),
  );
}
export async function finishSharedUpload(
  id: string,
  action: "complete" | "cancel",
): Promise<FileUploadResponse> {
  return uploadResult(
    await requestApi(`${ROOT}uploads/${encodeURIComponent(id)}/${action}/`, {
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
  const identity = await fileRequestIdentity(userId, "delete", body);
  const result = await requestApi(`${ROOT}deletion/`, {
    method: "POST",
    body: { ...body, request_id: identity.requestId },
  });
  if (
    !isRecord(result) ||
    result.request_id !== identity.requestId ||
    !isCount(result.deleted_count) ||
    !Array.isArray(result.deleted_paths) ||
    !result.deleted_paths.every((path) => typeof path === "string") ||
    !Array.isArray(result.missing_paths) ||
    !result.missing_paths.every((path) => typeof path === "string") ||
    result.deleted_count !== result.deleted_paths.length
  )
    return invalidResponse();
  finishFileRequest(identity);
  return result as unknown as FileDeleteResponse;
}
export async function downloadSharedFile(path: string): Promise<void> {
  const result = await requestApi(`${ROOT}downloads/`, {
    method: "POST",
    body: { path },
  });
  if (
    !isRecord(result) ||
    typeof result.transfer_id !== "string" ||
    !UUID.test(result.transfer_id) ||
    typeof result.expires_at !== "string" ||
    !isFile(result.file)
  )
    return invalidResponse();
  const transfer = result as unknown as FileDownloadResponse;
  const data = await requestApi(
    `${ROOT}downloads/${encodeURIComponent(transfer.transfer_id)}/`,
    { responseType: "blob", timeoutMs: 300000 },
  );
  if (
    !(data instanceof Blob) ||
    data.size !== transfer.file.size_bytes ||
    (await sha256(data)) !== transfer.file.sha256
  )
    throw new ApiError(
      "The downloaded file failed its integrity check. Download it again.",
    );
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = transfer.file.name;
  document.body.append(link);
  link.click();
  link.remove();
  // Leave enough time for the browser to accept the save request.
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
