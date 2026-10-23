// FileName: packages.ts

import { getSha256, saveBlob } from "@/app/files";

import { requestApi } from "./client";
import { isRecord, parsePaginationResponse, rejectInvalidResponse } from "./responses";
import { isRunSettings, cloneRunSettings, type RunSettings } from "./runSettings";
import {
  type PackageListEntryResponse,
  type PackageOptionEntryResponse,
  type PackageResponse,
  type PackageDetailsResponse,
  type PackageProjectGroupResponse,
  type PackageProjectGroupEntryResponse,
  type PackageProjectGroupListResponse,
  type ProjectPackageEntryResponse,
  type ProjectPackageListResponse,
  type PackageUploadResponse,
  type PackageReferenceResponse,
  type PackagePreparationResponse,
  PackageReferenceKind,
  PackagePreparationState,
  PackageUploadState,
} from "./generated/browserApi";

export type PackageListEntry = PackageListEntryResponse;
export type PackageOptionEntry = PackageOptionEntryResponse;
export type PackageInfo = PackageResponse;
export type PackageDetails = PackageDetailsResponse;
export type PackageProjectGroup = PackageProjectGroupResponse;
export type PackageProjectGroupEntry = PackageProjectGroupEntryResponse;
export type PackageProjectGroupPage = PackageProjectGroupListResponse;
export type ProjectPackagePage = ProjectPackageListResponse;
export type PackageReference = PackageReferenceResponse;
export type PackagePreparation = PackagePreparationResponse;
export type PackageUpload = PackageUploadResponse;
export type { PackageReferenceKind, PackagePreparationState, PackageUploadState };
export const PACKAGE_REFERENCE_LABELS: Record<PackageReferenceKind, string> = {
  schedule: "Schedule",
  job: "Job",
  preparation: "Preparation Request",
  download: "Download",
};

function isPackageListEntry(value: unknown): value is PackageListEntry {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.department_id === "string" &&
    typeof value.department_path === "string" &&
    typeof value.project_name === "string" &&
    typeof value.project_version === "string" &&
    typeof value.python_environment_name === "string" &&
    typeof value.can_manage === "boolean" &&
    typeof value.size_bytes === "number" &&
    typeof value.uploaded_at === "string" &&
    typeof value.uploaded_by_name === "string"
  );
}
export function isPackageInfo(value: unknown): value is PackageInfo {
  return (
    isRecord(value) &&
    isPackageListEntry(value) &&
    "settings" in value &&
    isRunSettings(value.settings) &&
    Array.isArray(value.api_input_keys) &&
    value.api_input_keys.every((name: unknown) => typeof name === "string") &&
    typeof value.description === "string" &&
    typeof value.version_summary === "string" &&
    typeof value.requires_liberrpa === "string" &&
    typeof value.sha256 === "string" &&
    isRecord(value.component_dependencies)
  );
}
function parsePackageDetails(value: unknown): PackageDetails {
  if (
    !isRecord(value) ||
    !isPackageInfo(value.package) ||
    !Array.isArray(value.preparation) ||
    !value.preparation.every(
      (preparation) =>
        isRecord(preparation) &&
        typeof preparation.executor_id === "string" &&
        typeof preparation.executor_name === "string" &&
        Object.values(PackagePreparationState).some(
          (state) => state === preparation.state,
        ) &&
        typeof preparation.reason === "string" &&
        typeof preparation.from_previous_association === "boolean",
    ) ||
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
    !Object.values(PackageUploadState).some((state) => state === value.state) ||
    typeof value.offset !== "number" ||
    typeof value.chunk_bytes !== "number" ||
    !(value.package === null || isPackageInfo(value.package))
  )
    return rejectInvalidResponse();
  return value as unknown as PackageUpload;
}
function isPackageProjectGroup(value: unknown): value is PackageProjectGroup {
  return (
    isRecord(value) &&
    typeof value.department_id === "string" &&
    typeof value.department_path === "string" &&
    typeof value.project_name === "string" &&
    typeof value.project_name_key === "string"
  );
}

function isPackageProjectGroupEntry(value: unknown): value is PackageProjectGroupEntry {
  return (
    isPackageProjectGroup(value) &&
    "latest_package_id" in value &&
    typeof value.latest_package_id === "string"
  );
}

export async function getPackageProjectGroups(
  departmentIds: string[],
  page = 1,
  locatePackageId?: string,
): Promise<PackageProjectGroupPage> {
  const query = new URLSearchParams({ page: String(page) });
  for (const strId of departmentIds) query.append("department_id", strId);
  if (locatePackageId) query.set("locate_package_id", locatePackageId);

  const response = await requestApi(`/packages/project-groups/?${query}`);
  if (
    !isRecord(response) ||
    !Array.isArray(response.project_groups) ||
    !response.project_groups.every(isPackageProjectGroupEntry)
  )
    return rejectInvalidResponse();

  return {
    project_groups: response.project_groups,
    ...parsePaginationResponse(response),
  };
}

export async function getProjectPackages(
  packageId: string,
  page?: number,
): Promise<ProjectPackagePage> {
  const query = page === undefined ? "" : `?page=${page}`;
  const response = await requestApi(
    `/packages/${encodeURIComponent(packageId)}/project-packages/${query}`,
  );
  if (
    !isRecord(response) ||
    !isPackageProjectGroup(response.project_group) ||
    !Array.isArray(response.packages) ||
    !response.packages.every(
      (packageEntry): packageEntry is ProjectPackageEntryResponse =>
        isRecord(packageEntry) &&
        typeof packageEntry.id === "string" &&
        typeof packageEntry.project_version === "string",
    )
  )
    return rejectInvalidResponse();

  return {
    project_group: response.project_group,
    packages: response.packages,
    ...parsePaginationResponse(response),
  };
}

export async function getPackageOptions(
  departmentId: string,
): Promise<PackageOptionEntry[]> {
  const response = await requestApi(
    `/packages/options/?${new URLSearchParams({ department_id: departmentId })}`,
  );
  if (
    !isRecord(response) ||
    !Array.isArray(response.packages) ||
    !response.packages.every(
      (packageEntry): packageEntry is PackageOptionEntry =>
        isPackageListEntry(packageEntry) &&
        "project_name_key" in packageEntry &&
        typeof packageEntry.project_name_key === "string",
    )
  )
    return rejectInvalidResponse();
  return response.packages;
}
export async function getPackageDetails(id: string): Promise<PackageDetails> {
  return parsePackageDetails(await requestApi(`/packages/${encodeURIComponent(id)}/`));
}
export async function savePackageSettings(
  id: string,
  environment: string,
  settings: RunSettings,
  apiInputKeys: string[],
): Promise<PackageDetails> {
  const response = await requestApi(`/packages/${encodeURIComponent(id)}/settings/`, {
    method: "POST",
    body: {
      python_environment_name: environment,
      settings: cloneRunSettings(settings),
      api_input_keys: [...apiInputKeys],
    },
  });
  return parsePackageDetails(response);
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
    { responseType: "blob" },
  );
  if (
    !(blob instanceof Blob) ||
    blob.size !== packageInfo.size_bytes ||
    (await getSha256(blob)) !== packageInfo.sha256
  )
    throw new Error("The package download failed its integrity check.");
  saveBlob(blob, response.file_name);
}
