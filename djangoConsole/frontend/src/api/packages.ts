// FileName: packages.ts

import { requestApi } from "./client";
import { isRecord, parsePaginationResponse, rejectInvalidResponse } from "./responses";
import { getSha256 } from "./sharedFiles";
import { isRunSettings, cloneRunSettings, type RunSettings } from "./runOptions";
import type { PaginationResponse } from "./generated/browserApi";

export interface PackageInfo {
  id: string;
  department_id: string;
  department_path: string;
  project_name: string;
  version: string;
  description: string;
  version_summary: string;
  requires_liberrpa: string;
  sha256: string;
  size_bytes: number;
  python_environment_name: string;
  settings: RunSettings;
  api_input_keys: string[];
  uploaded_at: string;
  uploaded_by_name: string;
  can_manage: boolean;
}
export enum PackageReferenceKind {
  Schedule = "schedule",
  Job = "job",
  Preparation = "preparation",
  Download = "download",
}
export const PACKAGE_REFERENCE_LABELS: Record<PackageReferenceKind, string> = {
  [PackageReferenceKind.Schedule]: "Schedule",
  [PackageReferenceKind.Job]: "Job",
  [PackageReferenceKind.Preparation]: "Preparation Request",
  [PackageReferenceKind.Download]: "Download",
};
export interface PackageReference {
  id: string;
  name: string;
  kind: PackageReferenceKind;
}
export interface PackagePreparation {
  executor_id: string;
  executor_name: string;
  state: string;
  reason: string;
}
export interface PackageDetails {
  package: PackageInfo;
  preparation: PackagePreparation[];
  references: PackageReference[];
}
export interface PackagePage extends PaginationResponse {
  packages: PackageInfo[];
}
export interface PackageUpload {
  upload_id: string;
  state: string;
  offset: number;
  size_bytes: number;
  chunk_bytes: number;
  expires_at: string;
  package: PackageInfo | null;
}
export function isPackageInfo(value: unknown): value is PackageInfo {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.department_id === "string" &&
    typeof value.project_name === "string" &&
    typeof value.version === "string" &&
    typeof value.python_environment_name === "string" &&
    isRunSettings(value.settings) &&
    Array.isArray(value.api_input_keys) &&
    value.api_input_keys.every((name: unknown) => typeof name === "string") &&
    typeof value.can_manage === "boolean" &&
    typeof value.size_bytes === "number"
  );
}
function parsePackageDetails(value: unknown): PackageDetails {
  if (
    !isRecord(value) ||
    !isPackageInfo(value.package) ||
    !Array.isArray(value.preparation) ||
    !Array.isArray(value.references) ||
    !value.references.every(
      (reference) =>
        isRecord(reference) &&
        typeof reference.id === "string" &&
        typeof reference.name === "string" &&
        Object.values(PackageReferenceKind).some((kind) => kind === reference.kind),
    )
  )
    return rejectInvalidResponse();
  return value as unknown as PackageDetails;
}
function parseUpload(value: unknown): PackageUpload {
  if (
    !isRecord(value) ||
    typeof value.upload_id !== "string" ||
    typeof value.state !== "string" ||
    typeof value.offset !== "number" ||
    typeof value.chunk_bytes !== "number" ||
    !(value.package === null || isPackageInfo(value.package))
  )
    return rejectInvalidResponse();
  return value as unknown as PackageUpload;
}
export async function getPackages(
  departmentIds: string[],
  name = "",
  page = 1,
): Promise<PackagePage> {
  const query = new URLSearchParams({ page: String(page), name });
  for (const strId of departmentIds) query.append("department_id", strId);
  const response = await requestApi(`/packages/?${query}`);
  if (
    !isRecord(response) ||
    !Array.isArray(response.packages) ||
    !response.packages.every(isPackageInfo)
  )
    return rejectInvalidResponse();
  return { packages: response.packages, ...parsePaginationResponse(response) };
}
export async function getPackageDetails(id: string): Promise<PackageDetails> {
  return parsePackageDetails(await requestApi(`/packages/${encodeURIComponent(id)}/`));
}
export async function savePackageSettings(
  id: string,
  environment: string,
  settings: RunSettings,
  apiInputKeys: string[],
): Promise<void> {
  await requestApi(`/packages/${encodeURIComponent(id)}/settings/`, {
    method: "POST",
    body: {
      python_environment_name: environment,
      settings: cloneRunSettings(settings),
      api_input_keys: [...apiInputKeys],
    },
  });
}
export async function cancelPackagePreparation(id: string): Promise<number> {
  const response = await requestApi(
    `/packages/${encodeURIComponent(id)}/preparations/cancel/`,
    { method: "POST", body: {} },
  );
  if (
    !isRecord(response) ||
    typeof response.canceled_count !== "number" ||
    !Number.isSafeInteger(response.canceled_count) ||
    response.canceled_count < 0
  )
    return rejectInvalidResponse();
  return response.canceled_count;
}
export async function deletePackage(id: string): Promise<void> {
  await requestApi(`/packages/${encodeURIComponent(id)}/delete/`, {
    method: "POST",
    body: {},
  });
}
export async function createPackageUpload(
  file: File,
  departmentId: string,
  requestId: string,
): Promise<PackageUpload> {
  return parseUpload(
    await requestApi("/packages/uploads/", {
      method: "POST",
      body: {
        department_id: departmentId,
        request_id: requestId,
        size_bytes: file.size,
        sha256: await getSha256(file),
      },
    }),
  );
}
export async function getPackageUpload(id: string): Promise<PackageUpload> {
  return parseUpload(await requestApi(`/packages/uploads/${encodeURIComponent(id)}/`));
}
export async function appendPackageChunk(
  id: string,
  offset: number,
  chunk: Blob,
): Promise<PackageUpload> {
  return parseUpload(
    await requestApi(`/packages/uploads/${encodeURIComponent(id)}/chunks/${offset}/`, {
      method: "PUT",
      body: chunk,
      headers: { "X-Chunk-SHA256": await getSha256(chunk) },
      timeoutMs: 120000,
    }),
  );
}
export async function finishPackageUpload(
  id: string,
  action: "complete" | "cancel",
): Promise<PackageUpload> {
  return parseUpload(
    await requestApi(`/packages/uploads/${encodeURIComponent(id)}/${action}/`, {
      method: "POST",
      body: {},
      timeoutMs: 120000,
    }),
  );
}
export function saveBlob(blob: Blob, name: string): void {
  const strUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = strUrl;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(strUrl), 60000);
}
export async function downloadPackage(packageInfo: PackageInfo): Promise<void> {
  const response = await requestApi(
    `/packages/${encodeURIComponent(packageInfo.id)}/downloads/`,
    { method: "POST", body: {} },
  );
  if (
    !isRecord(response) ||
    typeof response.transfer_id !== "string" ||
    typeof response.file_name !== "string" ||
    !response.file_name.endsWith(".rpa.zip")
  )
    return rejectInvalidResponse();
  const blob = await requestApi(
    `/packages/downloads/${encodeURIComponent(response.transfer_id)}/content/`,
    { responseType: "blob", timeoutMs: 300000 },
  );
  if (
    !(blob instanceof Blob) ||
    blob.size !== packageInfo.size_bytes ||
    (await getSha256(blob)) !== packageInfo.sha256
  )
    throw new Error("The package download failed its integrity check.");
  saveBlob(blob, response.file_name);
}
