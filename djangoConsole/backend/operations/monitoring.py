# FileName: monitoring.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import math
import re
import time
from datetime import datetime, UTC
from http.client import HTTPException
from typing import Literal
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from console_project.config import MonitoringConfig

from .contracts import (
    InstanceHistoryRange,
    InstanceMetricsResponse,
    InstanceHistorySampleResponse,
    InstanceStatusResponse,
)

_HISTORY_INTERVALS = {
    InstanceHistoryRange.HOUR: (3600, 60),
    InstanceHistoryRange.DAY: (86400, 300),
    InstanceHistoryRange.WEEK: (604800, 900),
    InstanceHistoryRange.FIFTEEN_DAYS: (1296000, 1800),
}
_METRIC_FIELDS = tuple(InstanceMetricsResponse.model_fields)
_HOST_LABELS = 'job="liberrpa-host",instance="console"'
_INT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_INT_REQUEST_TIMEOUT_SECONDS = 5
_INT_MAX_SAMPLE_AGE_SECONDS = 180


class MonitoringUnavailableError(Exception):
    pass


def _query_prometheus(
    monitoringConfig: MonitoringConfig,
    queryType: Literal["query", "query_range", "series"],
    parameters: dict[str, str | int],
) -> list[dict]:
    strUrl = (
        f"{str(monitoringConfig.prometheusUrl).rstrip('/')}/api/v1/{queryType}?"
        f"{urlencode(parameters)}"
    )
    try:
        with urlopen(
            Request(strUrl, headers={"Accept": "application/json"}),
            timeout=_INT_REQUEST_TIMEOUT_SECONDS,
        ) as response:
            responseBody = response.read(_INT_MAX_RESPONSE_BYTES + 1)
        if len(responseBody) > _INT_MAX_RESPONSE_BYTES:
            raise MonitoringUnavailableError("Prometheus response is too large.")
        result = json.loads(responseBody)
    except (URLError, OSError, HTTPException) as e:
        raise MonitoringUnavailableError("Prometheus could not be reached.") from e
    except (ValueError, UnicodeError, RecursionError) as e:
        raise MonitoringUnavailableError("Prometheus returned invalid JSON.") from e

    if not isinstance(result, dict) or result.get("status") != "success":
        raise MonitoringUnavailableError("Prometheus did not complete the query.")
    resultData = result.get("data")
    if queryType == "series":
        listSeries = resultData
    else:
        strExpectedType = "vector" if queryType == "query" else "matrix"
        if (
            not isinstance(resultData, dict)
            or resultData.get("resultType") != strExpectedType
        ):
            raise MonitoringUnavailableError("Prometheus returned an invalid result.")
        listSeries = resultData.get("result")
    if not isinstance(listSeries, list) or any(
        not isinstance(series, dict) for series in listSeries
    ):
        raise MonitoringUnavailableError("Prometheus returned an invalid series list.")
    return listSeries


def _parse_sample(sample: object) -> tuple[float, float | None]:
    if (
        not isinstance(sample, list)
        or len(sample) != 2
        or type(sample[0]) not in (int, float)
        or not isinstance(sample[1], str)
    ):
        raise MonitoringUnavailableError("Prometheus returned an invalid sample.")
    try:
        floatTimestamp = float(sample[0])
        floatValue = float(sample[1])
    except (ValueError, OverflowError) as e:
        raise MonitoringUnavailableError("Prometheus returned an invalid sample.") from e
    if not math.isfinite(floatTimestamp):
        raise MonitoringUnavailableError("Prometheus returned an invalid sample time.")
    return floatTimestamp, floatValue if math.isfinite(floatValue) else None


def load_instance_status(
    monitoringConfig: MonitoringConfig | None,
    historyRange: InstanceHistoryRange,
    networkInterface: str | None,
) -> InstanceStatusResponse:
    intDuration, intInterval = _HISTORY_INTERVALS[historyRange]
    dictEmptyMetric: dict[str, float | None] = dict.fromkeys(_METRIC_FIELDS, None)
    if monitoringConfig is None:
        return InstanceStatusResponse(
            configured=False,
            range=historyRange,
            interval_seconds=intInterval,
            network_interfaces=[],
            network_interface=None,
            collected_at=None,
            current=InstanceMetricsResponse(**dictEmptyMetric),
            history=[],
        )

    def get_metric_value(metricName: str, sampleValue: float | None) -> float | None:
        if sampleValue is None or sampleValue < 0:
            return None
        if metricName in ("cpu_percent", "memory_percent") and sampleValue > 100:
            return None
        return sampleValue

    intNow = int(time.time())
    intEnd = intNow // 60 * 60
    intStart = intEnd - intDuration + intInterval
    listCurrentSeries = _query_prometheus(
        monitoringConfig,
        "query",
        {
            "query": f'{{__name__=~"liberrpa_host_.*",{_HOST_LABELS}}}',
            "time": intNow,
        },
    )
    dictCurrentValue: dict[tuple[str, str], float | None] = {}
    setNetworkInterface: set[str] = set()
    for series in listCurrentSeries:
        labels = series.get("metric")
        if not isinstance(labels, dict):
            raise MonitoringUnavailableError("Prometheus returned invalid metric labels.")
        strMetric = labels.get("metric")
        if strMetric not in (*_METRIC_FIELDS, "up", "scraped_at_seconds"):
            continue
        strDevice = labels.get("device", "")
        if not isinstance(strDevice, str):
            raise MonitoringUnavailableError("Prometheus returned an invalid interface.")
        _, floatValue = _parse_sample(series.get("value"))
        dictCurrentValue[(strMetric, strDevice)] = floatValue
        if strMetric.startswith("network_") and strDevice and strDevice != "lo":
            setNetworkInterface.add(strDevice)

    # An offline host may have no current series, but its earlier network history remains useful.
    if not setNetworkInterface:
        listNetworkSeries = _query_prometheus(
            monitoringConfig,
            "series",
            {
                "match[]": f"liberrpa_host_network_receive_bytes_per_second{{{_HOST_LABELS}}}",
                "start": intEnd - intDuration,
                "end": intNow,
            },
        )
        for labels in listNetworkSeries:
            strDevice = labels.get("device")
            if isinstance(strDevice, str) and strDevice and strDevice != "lo":
                setNetworkInterface.add(strDevice)
    if networkInterface is not None:
        setNetworkInterface.add(networkInterface)
    listNetworkInterface = sorted(setNetworkInterface)
    strNetworkInterface = networkInterface or next(iter(listNetworkInterface), None)

    dictCurrentMetric = dictEmptyMetric.copy()
    collectedAt = None
    floatScrapedAt = dictCurrentValue.get(("scraped_at_seconds", ""))
    if (
        dictCurrentValue.get(("up", "")) == 1
        and floatScrapedAt is not None
        and 0 <= intNow - floatScrapedAt <= _INT_MAX_SAMPLE_AGE_SECONDS
    ):
        collectedAt = datetime.fromtimestamp(floatScrapedAt, UTC)
        for strMetric in _METRIC_FIELDS:
            strDevice = (
                (strNetworkInterface or "") if strMetric.startswith("network_") else ""
            )
            dictCurrentMetric[strMetric] = get_metric_value(
                strMetric, dictCurrentValue.get((strMetric, strDevice))
            )

    # Match an absent device label for CPU/memory and the selected interface for network metrics.
    strDevicePattern = (
        "|" + re.sub(r"([\\.^$|?*+()\[\]{}])", r"\\\1", strNetworkInterface)
        if strNetworkInterface is not None
        else ""
    )
    strMetricPattern = "|".join(f"liberrpa_host_{name}" for name in _METRIC_FIELDS)
    strHistorySelector = (
        f"{{__name__=~{json.dumps(strMetricPattern)},{_HOST_LABELS},"
        f"device=~{json.dumps(strDevicePattern)}}}"
    )
    listHistorySeries = _query_prometheus(
        monitoringConfig,
        "query_range",
        {
            "query": f"max_over_time({strHistorySelector}[{intInterval}s])",
            "start": intStart,
            "end": intEnd,
            "step": intInterval,
        },
    )
    dictHistoryMetric: dict[int, dict[str, float | None]] = {
        intTimestamp: dictEmptyMetric.copy()
        for intTimestamp in range(intStart, intEnd + 1, intInterval)
    }
    for series in listHistorySeries:
        labels = series.get("metric")
        listSample = series.get("values")
        if not isinstance(labels, dict) or not isinstance(listSample, list):
            raise MonitoringUnavailableError("Prometheus returned invalid history.")
        strMetric = labels.get("metric")
        if strMetric not in _METRIC_FIELDS:
            continue
        if (
            strMetric.startswith("network_")
            and labels.get("device") != strNetworkInterface
        ):
            continue
        for sample in listSample:
            floatTimestamp, floatValue = _parse_sample(sample)
            if floatTimestamp.is_integer() and int(floatTimestamp) in dictHistoryMetric:
                dictHistoryMetric[int(floatTimestamp)][strMetric] = get_metric_value(
                    strMetric, floatValue
                )

    return InstanceStatusResponse(
        configured=True,
        range=historyRange,
        interval_seconds=intInterval,
        network_interfaces=listNetworkInterface,
        network_interface=strNetworkInterface,
        collected_at=collectedAt,
        current=InstanceMetricsResponse(**dictCurrentMetric),
        history=[
            InstanceHistorySampleResponse(
                timestamp=datetime.fromtimestamp(intTimestamp, UTC), **dictMetric
            )
            for intTimestamp, dictMetric in dictHistoryMetric.items()
        ],
    )
