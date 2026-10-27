// FileName: packages.ts

import { getSha256, downloadFile } from "@/app/files";

import { requestApi } from "./client";
import { ApiError } from "./errors";
import { isRecord, rejectInvalidResponse } from "./responses";
import { cloneRunSettings, type RunSettings } from "./runSettings";
import {
  type PackageDetailsResponse,
  type PackageOptionEntryResponse,
  type PackageOptionsResponse,
  type PackageProjectGroupListResponse,
  type PackageUploadResponse,
  type ProjectPackageListResponse,
  type PackageReferenceKind,
  type PackagePreparationState,
  INT_MAX_PACKAGE_BYTES,
  PackageUploadState,
} from "./generated/browserApi";

export type { PackageReferenceKind, PackagePreparationState, PackageUploadState };
export const PACKAGE_REFERENCE_LABELS: Record<PackageReferenceKind, string> = {
  schedule: "Schedule",
  job: "Job",
  preparation: "Preparation Request",
  download: "Download",
};

function parseUpload(value: unknown): PackageUploadResponse {
  if (
    !isRecord(value) ||
    typeof value.upload_id !== "string" ||
    !Object.values(PackageUploadState).some((state) => state === value.state) ||
    typeof value.offset !== "number" ||
    typeof value.chunk_bytes !== "number" ||
    !(
      value.package === null ||
      (isRecord(value.package) &&
        typeof value.package.id === "string" &&
        typeof value.package.department_id === "string")
    )
  )
    return rejectInvalidResponse();
  return value as unknown as PackageUploadResponse;
}
export async function getPackageProjectGroups(
  departmentIds: string[],
  page = 1,
  locatePackageId?: string,
): Promise<PackageProjectGroupListResponse> {
  const query = new URLSearchParams({ page: String(page) });
  for (const strId of departmentIds) query.append("department_id", strId);
  if (locatePackageId) query.set("locate_package_id", locatePackageId);

  return requestApi<PackageProjectGroupListResponse>(`/packages/project-groups/?${query}`);
}

export async function getProjectPackages(
  packageId: string,
  page?: number,
): Promise<ProjectPackageListResponse> {
  const query = page === undefined ? "" : `?page=${page}`;
  return requestApi<ProjectPackageListResponse>(
    `/packages/${encodeURIComponent(packageId)}/project-packages/${query}`,
  );
}

export async function getPackageOptions(
  departmentId: string,
): Promise<PackageOptionEntryResponse[]> {
  const response = await requestApi<PackageOptionsResponse>(
    `/packages/options/?${new URLSearchParams({ department_id: departmentId })}`,
  );
  return response.packages;
}
export async function getPackageDetails(id: string): Promise<PackageDetailsResponse> {
  return requestApi<PackageDetailsResponse>(`/packages/${encodeURIComponent(id)}/`);
}
export async function savePackageSettings(
  id: string,
  environment: string,
  settings: RunSettings,
  apiInputKeys: string[],
): Promise<PackageDetailsResponse> {
  return requestApi<PackageDetailsResponse>(
    `/packages/${encodeURIComponent(id)}/settings/`,
    {
      method: "POST",
      body: {
        python_environment_name: environment,
        settings: cloneRunSettings(settings),
        api_input_keys: [...apiInputKeys],
      },
    },
  );
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
): Promise<PackageUploadResponse> {
  if (file.size === 0 || file.size > INT_MAX_PACKAGE_BYTES) {
    throw new ApiError(
      `Select a non-empty package ZIP no larger than ${INT_MAX_PACKAGE_BYTES / 1024 ** 2} MiB.`,
      { code: "invalid_file_size" },
    );
  }
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
export async function getPackageUpload(id: string): Promise<PackageUploadResponse> {
  return parseUpload(await requestApi(`/packages/uploads/${encodeURIComponent(id)}/`));
}
export async function appendPackageChunk(
  id: string,
  offset: number,
  chunk: Blob,
): Promise<PackageUploadResponse> {
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
): Promise<PackageUploadResponse> {
  return parseUpload(
    await requestApi(`/packages/uploads/${encodeURIComponent(id)}/${action}/`, {
      method: "POST",
      body: {},
      timeoutMs: 120000,
    }),
  );
}
export async function downloadPackage(packageId: string): Promise<void> {
  const response = await requestApi(
    `/packages/${encodeURIComponent(packageId)}/downloads/`,
    { method: "POST", body: {} },
  );
  if (
    !isRecord(response) ||
    typeof response.transfer_id !== "string" ||
    typeof response.file_name !== "string" ||
    !response.file_name.endsWith(".rpa.zip")
  )
    return rejectInvalidResponse();
  downloadFile(
    `/api/packages/downloads/${encodeURIComponent(response.transfer_id)}/content/`,
    response.file_name,
  );
}
