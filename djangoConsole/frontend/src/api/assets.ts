// FileName: assets.ts

import { requestApi } from "./client";
import { rejectInvalidResponse, parseMessageResponse } from "./responses";

import type {
  AssetType,
  OrdinaryAssetType,
  AssetCreationRequest,
  AssetListResponse,
  AssetDetailsResponse,
  AssetUpdateRequest,
} from "./generated/browserApi";
import { ARR_ASSET_TYPE_VALUE, ARR_ORDINARY_ASSET_TYPE } from "./generated/browserApi";

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

function parseAssetDetails(payload: AssetDetailsResponse): AssetDetailsResponse {
  if (isSecretAsset(payload.asset.asset_type)) {
    if ("value" in payload.asset) return rejectInvalidResponse();
  } else if (!("value" in payload.asset)) return rejectInvalidResponse();
  return payload;
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
  return requestApi<AssetListResponse>(`/assets/?${query}`);
}

export async function getAssetDetails(assetId: string): Promise<AssetDetailsResponse> {
  return parseAssetDetails(
    await requestApi<AssetDetailsResponse>(`/assets/${encodeURIComponent(assetId)}/`),
  );
}

export async function createAsset(
  payload: AssetCreationRequest,
): Promise<AssetDetailsResponse> {
  return parseAssetDetails(
    await requestApi<AssetDetailsResponse>("/assets/", { method: "POST", body: payload }),
  );
}

export async function updateAsset(
  assetId: string,
  payload: AssetUpdateRequest,
): Promise<AssetDetailsResponse> {
  return parseAssetDetails(
    await requestApi<AssetDetailsResponse>(`/assets/${encodeURIComponent(assetId)}/`, {
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
