// FileName: instanceStatus.ts

import { requestApi } from "./client";
import {
  isRecord,
  isDateString,
  isNullableDateString,
  isNonnegativeInteger,
  isNullableString,
  rejectInvalidResponse,
} from "./responses";

import {
  ARR_INSTANCE_HEALTH_STATUS,
  ARR_INSTANCE_COMPONENT,
  type InstanceComponentResponse,
  type InstanceStorageResponse,
  type InstanceSummaryResponse,
  ARR_INSTANCE_HISTORY_RANGE,
  type InstanceHistoryRange,
  type InstanceHistorySampleResponse,
  type InstanceMetricsResponse,
  type InstanceStatusResponse,
} from "./generated/browserApi";

export async function getInstanceSummary(): Promise<InstanceSummaryResponse> {
  function isComponent(value: unknown): value is InstanceComponentResponse {
    return (
      isRecord(value) &&
      ARR_INSTANCE_COMPONENT.some((component) => component === value.component) &&
      ARR_INSTANCE_HEALTH_STATUS.some((status) => status === value.status) &&
      isNullableDateString(value.checked_at) &&
      typeof value.message === "string"
    );
  }

  function isStorage(value: unknown): value is InstanceStorageResponse {
    return (
      isRecord(value) &&
      [value.total_bytes, value.used_bytes, value.free_bytes].every(
        (bytes) => bytes === null || isNonnegativeInteger(bytes),
      ) &&
      ARR_INSTANCE_HEALTH_STATUS.some((status) => status === value.status) &&
      isDateString(value.checked_at) &&
      typeof value.message === "string"
    );
  }

  const payload = await requestApi("/platform/instance-status/summary/");
  if (
    !isRecord(payload) ||
    !isDateString(payload.updated_at) ||
    typeof payload.time_zone !== "string" ||
    !payload.time_zone ||
    !Array.isArray(payload.components) ||
    !payload.components.every(isComponent) ||
    payload.components.length !== ARR_INSTANCE_COMPONENT.length ||
    new Set(payload.components.map((component) => component.component)).size !==
      ARR_INSTANCE_COMPONENT.length ||
    !isStorage(payload.storage)
  )
    return rejectInvalidResponse();

  return {
    updated_at: payload.updated_at,
    time_zone: payload.time_zone,
    components: payload.components,
    storage: payload.storage,
  };
}

function isInstanceMetrics(value: unknown): value is InstanceMetricsResponse {
  function isNullableMetric(metric: unknown, maximum = Infinity): boolean {
    return (
      metric === null ||
      (typeof metric === "number" &&
        Number.isFinite(metric) &&
        metric >= 0 &&
        metric <= maximum)
    );
  }

  return (
    isRecord(value) &&
    isNullableMetric(value.cpu_percent, 100) &&
    isNullableMetric(value.memory_percent, 100) &&
    isNullableMetric(value.network_receive_bytes_per_second) &&
    isNullableMetric(value.network_transmit_bytes_per_second)
  );
}

export async function getInstanceStatus(
  range: InstanceHistoryRange,
  networkInterface: string | null,
): Promise<InstanceStatusResponse> {
  const parameters = new URLSearchParams({ range });
  if (networkInterface) parameters.set("network_interface", networkInterface);
  const payload = await requestApi(`/platform/instance-status/?${parameters}`, {
    timeoutMs: 20000,
  });

  if (!isRecord(payload)) return rejectInvalidResponse();
  const historyRange = ARR_INSTANCE_HISTORY_RANGE.find((value) => value === payload.range);
  if (
    typeof payload.configured !== "boolean" ||
    historyRange === undefined ||
    !isNonnegativeInteger(payload.interval_seconds) ||
    payload.interval_seconds === 0 ||
    !Array.isArray(payload.network_interfaces) ||
    !payload.network_interfaces.every(
      (value: unknown): value is string => typeof value === "string",
    ) ||
    !isNullableString(payload.network_interface) ||
    !isNullableDateString(payload.collected_at) ||
    !isInstanceMetrics(payload.current) ||
    !Array.isArray(payload.history) ||
    !payload.history.every(
      (sample: unknown): sample is InstanceHistorySampleResponse =>
        isRecord(sample) && isDateString(sample.timestamp) && isInstanceMetrics(sample),
    )
  )
    return rejectInvalidResponse();

  return {
    configured: payload.configured,
    range: historyRange,
    interval_seconds: payload.interval_seconds,
    network_interfaces: payload.network_interfaces,
    network_interface: payload.network_interface,
    collected_at: payload.collected_at,
    current: payload.current,
    history: payload.history,
  };
}
