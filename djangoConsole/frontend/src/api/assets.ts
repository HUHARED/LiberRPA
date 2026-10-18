// FileName: assets.ts

import { requestApi } from "./client";
import {
  isRecord,
  rejectInvalidResponse,
  parsePaginationResponse,
  parseMessageResponse,
} from "./responses";

import type {
  AssetType,
  OrdinaryAssetType,
  AssetCreationRequest,
  AssetEntryResponse,
  AssetListResponse,
  AssetDetailsResponse,
  AssetUpdateRequest,
  AssetReferenceResponse,
} from "./generated/browserApi";
import {
  ARR_ASSET_TYPE_VALUE,
  ARR_ORDINARY_ASSET_TYPE,
  ARR_ASSET_REFERENCE_KIND,
} from "./generated/browserApi";

const DICT_ASSET_TYPE_LABEL: Record<AssetType, string> = {
  text: "Text",
  integer: "Integer",
  number: "Number",
  boolean: "Boolean",
  json: "JSON",
  secret_text: "Secret Text",
  credential: "Credential",
};
export const ARR_ASSET_TYPE: { title: string; value: AssetType }[] =
  ARR_ASSET_TYPE_VALUE.map((value) => ({ title: DICT_ASSET_TYPE_LABEL[value], value }));

export interface AssetListFilters {
  name: string;
  departmentIds: string[];
  assetTypes: AssetType[];
}

export function isOrdinaryAssetType(value: unknown): value is OrdinaryAssetType {
  return ARR_ORDINARY_ASSET_TYPE.some((assetType) => assetType === value);
}

export function isSecretAsset(assetType: AssetType): boolean {
  return !isOrdinaryAssetType(assetType);
}

export function getAssetTypeLabel(assetType: AssetType): string {
  return DICT_ASSET_TYPE_LABEL[assetType];
}

function isAssetEntry(value: unknown): value is AssetEntryResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    isRecord(value.department) &&
    typeof value.department.id === "string" &&
    typeof value.department.path === "string" &&
    typeof value.path === "string" &&
    ARR_ASSET_TYPE_VALUE.some((assetType) => assetType === value.asset_type) &&
    typeof value.notes === "string" &&
    typeof value.value_summary === "string" &&
    typeof value.can_manage === "boolean" &&
    typeof value.can_edit_value === "boolean" &&
    typeof value.created_at === "string" &&
    Number.isFinite(Date.parse(value.created_at)) &&
    typeof value.updated_at === "string" &&
    Number.isFinite(Date.parse(value.updated_at))
  );
}

function parseAssetDetails(payload: unknown): AssetDetailsResponse {
  if (
    !isRecord(payload) ||
    !isAssetEntry(payload.asset) ||
    !("references" in payload.asset) ||
    !Array.isArray(payload.asset.references) ||
    !payload.asset.references.every(
      (reference: unknown): reference is AssetReferenceResponse =>
        isRecord(reference) &&
        ARR_ASSET_REFERENCE_KIND.some((kind) => kind === reference.kind) &&
        typeof reference.id === "string" &&
        typeof reference.name === "string" &&
        (reference.project_version === null ||
          typeof reference.project_version === "string"),
    )
  )
    return rejectInvalidResponse();
  if (isSecretAsset(payload.asset.asset_type)) {
    if ("value" in payload.asset) return rejectInvalidResponse();
  } else if (!("value" in payload.asset)) return rejectInvalidResponse();
  return { asset: { ...payload.asset, references: payload.asset.references } };
}

export async function getAssetList(
  filters: AssetListFilters,
  page: number,
): Promise<AssetListResponse> {
  const query = new URLSearchParams({ page: String(page) });
  if (filters.name) query.set("name", filters.name);
  for (const strDepartmentId of filters.departmentIds)
    query.append("department_id", strDepartmentId);
  for (const strAssetType of filters.assetTypes) query.append("type", strAssetType);
  const payload = await requestApi(`/assets/?${query}`);
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.assets) ||
    !payload.assets.every(isAssetEntry)
  )
    return rejectInvalidResponse();
  return {
    assets: payload.assets,
    ...parsePaginationResponse(payload),
  };
}

export async function getAssetDetails(assetId: string): Promise<AssetDetailsResponse> {
  return parseAssetDetails(await requestApi(`/assets/${encodeURIComponent(assetId)}/`));
}

export async function createAsset(
  payload: AssetCreationRequest,
): Promise<AssetDetailsResponse> {
  return parseAssetDetails(await requestApi("/assets/", { method: "POST", body: payload }));
}

export async function updateAsset(
  assetId: string,
  payload: AssetUpdateRequest,
): Promise<AssetDetailsResponse> {
  return parseAssetDetails(
    await requestApi(`/assets/${encodeURIComponent(assetId)}/`, {
      method: "POST",
      body: payload,
    }),
  );
}

export async function deleteAsset(assetId: string): Promise<void> {
  const payload = await requestApi(`/assets/${encodeURIComponent(assetId)}/deletion/`, {
    method: "POST",
    body: {},
  });
  parseMessageResponse(payload);
}
