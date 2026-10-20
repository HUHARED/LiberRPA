// FileName: organizationLimits.ts

import { LimitUnit } from "@/api/generated/browserApi";

import { formatFileSize } from "./formatters";

export function formatOrganizationLimit(value: number | null, unit: LimitUnit): string {
  if (value === null) return "—";
  if (unit === LimitUnit.Bytes) return formatFileSize(value);
  const strValue = value.toLocaleString("en");
  return unit === LimitUnit.PerMinute ? `${strValue} / min` : strValue;
}
