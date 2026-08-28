// FileName: time.ts

import moment from "moment-timezone";

import { getSystemIntlTimezone, isSupportedIntlTimezone } from "../../../shared/timezone";

const STR_DISPLAY_DATETIME_FORMAT = "YYYY-MM-DD HH:mm:ss";
const STR_DATETIME_LOCAL_FORMAT_MINUTE = "YYYY-MM-DDTHH:mm";
const STR_DATETIME_LOCAL_FORMAT_SECOND = "YYYY-MM-DDTHH:mm:ss";
const STR_DEFAULT_PERIOD_END_LOCAL = "2084-04-04T00:00:00";

function isValidTimezone(timezone: string): boolean {
  return moment.tz.zone(timezone) !== null && isSupportedIntlTimezone(timezone);
}

export const arrTimezone = moment.tz.names().filter(isValidTimezone);

export function getSystemTimezone(): string {
  const strTimezone = getSystemIntlTimezone();
  return isValidTimezone(strTimezone) ? strTimezone : "UTC";
}

export function formatTimestamp(timestampMs: number | null, timezone: string): string {
  if (timestampMs === null) {
    return "Unknown";
  }

  if (!Number.isSafeInteger(timestampMs) || timestampMs < 0 || !isValidTimezone(timezone)) {
    return "Invalid time";
  }

  return moment.tz(timestampMs, timezone).format(STR_DISPLAY_DATETIME_FORMAT);
}

export function formatTimestampForDateTimeLocal(
  timestampMs: number,
  timezone: string,
): string {
  if (!Number.isSafeInteger(timestampMs) || timestampMs < 0 || !isValidTimezone(timezone)) {
    return "";
  }

  return moment.tz(timestampMs, timezone).format(STR_DATETIME_LOCAL_FORMAT_SECOND);
}

export function parseDateTimeLocalToTimestamp(
  dateTimeLocal: string,
  timezone: string,
): number | undefined {
  if (!isValidTimezone(timezone)) {
    return undefined;
  }

  const strFormat =
    dateTimeLocal.length === STR_DATETIME_LOCAL_FORMAT_MINUTE.length
      ? STR_DATETIME_LOCAL_FORMAT_MINUTE
      : dateTimeLocal.length === STR_DATETIME_LOCAL_FORMAT_SECOND.length
        ? STR_DATETIME_LOCAL_FORMAT_SECOND
        : undefined;
  if (strFormat === undefined) {
    return undefined;
  }

  const momentObj = moment.tz(dateTimeLocal, strFormat, true, timezone);
  if (!momentObj.isValid() || momentObj.format(strFormat) !== dateTimeLocal) {
    return undefined;
  }

  const intTimestampMs = momentObj.valueOf();
  return Number.isSafeInteger(intTimestampMs) && intTimestampMs >= 0
    ? intTimestampMs
    : undefined;
}

export function getDefaultSchedulePeriod(timezone: string): {
  periodStartLocal: string;
  periodEndLocal: string;
} {
  if (!isValidTimezone(timezone)) {
    throw new Error(`Invalid Executor time zone: ${timezone}`);
  }

  return {
    periodStartLocal: moment
      .tz(timezone)
      .startOf("day")
      .format(STR_DATETIME_LOCAL_FORMAT_SECOND),
    periodEndLocal: STR_DEFAULT_PERIOD_END_LOCAL,
  };
}
