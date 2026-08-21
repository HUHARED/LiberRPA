// FileName: dateTime.ts

import moment from "moment-timezone";

const STR_DATE_TIME_LOCAL_FORMAT_MINUTE = "YYYY-MM-DDTHH:mm";
const STR_DATE_TIME_LOCAL_FORMAT_SECOND = "YYYY-MM-DDTHH:mm:ss";
const STR_DATE_TIME_DISPLAY_FORMAT = "YYYY-MM-DD HH:mm:ss";

export function isValidTimeZone(strTimezone: string): boolean {
  if (moment.tz.zone(strTimezone) === null) {
    return false;
  }

  try {
    new Intl.DateTimeFormat("en-US", { timeZone: strTimezone }).format();
    return true;
  } catch (e: unknown) {
    if (e instanceof RangeError) {
      return false;
    }
    throw e;
  }
}

export function formatTimestampMs(intTimestampMs: number, strTimezone: string): string {
  if (!Number.isSafeInteger(intTimestampMs) || !isValidTimeZone(strTimezone)) {
    return "Invalid time";
  }
  return moment.tz(intTimestampMs, strTimezone).format(STR_DATE_TIME_DISPLAY_FORMAT);
}

export function formatNullableTimestampMs(
  intTimestampMs: number | null,
  strTimezone: string,
): string {
  if (intTimestampMs === null) {
    return "Unknown";
  }
  return formatTimestampMs(intTimestampMs, strTimezone);
}

export function formatTimestampMsForDateTimeLocal(
  intTimestampMs: number,
  strTimezone: string,
): string {
  if (!Number.isSafeInteger(intTimestampMs) || !isValidTimeZone(strTimezone)) {
    return "";
  }
  return moment.tz(intTimestampMs, strTimezone).format(STR_DATE_TIME_LOCAL_FORMAT_SECOND);
}

export function parseDateTimeLocalToTimestampMs(
  strDateTimeLocal: string,
  strTimezone: string,
): number | null {
  if (!isValidTimeZone(strTimezone)) {
    return null;
  }

  const strFormat =
    strDateTimeLocal.length === 16
      ? STR_DATE_TIME_LOCAL_FORMAT_MINUTE
      : strDateTimeLocal.length === 19
        ? STR_DATE_TIME_LOCAL_FORMAT_SECOND
        : undefined;
  if (strFormat === undefined) {
    return null;
  }

  const momentObj = moment.tz(strDateTimeLocal, strFormat, true, strTimezone);
  if (!momentObj.isValid() || momentObj.format(strFormat) !== strDateTimeLocal) {
    return null;
  }

  return momentObj.valueOf();
}

export function isSchedulerPeriodValid(
  strPeriodStart: string,
  strPeriodEnd: string,
  strTimezone: string,
): boolean {
  const intPeriodStartMs = parseDateTimeLocalToTimestampMs(strPeriodStart, strTimezone);
  const intPeriodEndMs = parseDateTimeLocalToTimestampMs(strPeriodEnd, strTimezone);
  return (
    intPeriodStartMs !== null &&
    intPeriodEndMs !== null &&
    intPeriodEndMs > intPeriodStartMs
  );
}

export function createDefaultSchedulerPeriod(strTimezone: string): {
  periodStart: string;
  periodEnd: string;
} {
  if (!isValidTimeZone(strTimezone)) {
    throw new Error(`Invalid time zone: ${strTimezone}`);
  }

  const momentObjPeriodStart = moment().tz(strTimezone).startOf("day");
  const momentObjPeriodEnd = moment.tz(
    "2084-04-04T00:00:00",
    STR_DATE_TIME_LOCAL_FORMAT_SECOND,
    true,
    strTimezone,
  );

  return {
    periodStart: momentObjPeriodStart.format(STR_DATE_TIME_LOCAL_FORMAT_SECOND),
    periodEnd: momentObjPeriodEnd.format(STR_DATE_TIME_LOCAL_FORMAT_SECOND),
  };
}
