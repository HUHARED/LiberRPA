import moment from "moment-timezone";

const STR_DISPLAY_DATETIME_FORMAT = "YYYY-MM-DD HH:mm:ss";
const STR_DATETIME_LOCAL_FORMAT_MINUTE = "YYYY-MM-DDTHH:mm";
const STR_DATETIME_LOCAL_FORMAT_SECOND = "YYYY-MM-DDTHH:mm:ss";
const STR_DEFAULT_PERIOD_END_LOCAL = "2084-04-04T00:00:00";

function isSupportedIntlTimezone(strTimezone: string): boolean {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: strTimezone }).format();
    return true;
  } catch {
    return false;
  }
}

export function isValidTimezone(strTimezone: string): boolean {
  return moment.tz.zone(strTimezone) !== null && isSupportedIntlTimezone(strTimezone);
}

export const arrTimezone = moment.tz.names().filter(isValidTimezone);

export function getSystemTimezone(): string {
  const strTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return isValidTimezone(strTimezone) ? strTimezone : "UTC";
}

export function formatTimestamp(
  intTimestampMs: number | null,
  strTimezone: string,
): string {
  if (intTimestampMs === null) {
    return "Unknown";
  }

  if (
    !Number.isSafeInteger(intTimestampMs) ||
    intTimestampMs < 0 ||
    !isValidTimezone(strTimezone)
  ) {
    return "Invalid time";
  }

  return moment.tz(intTimestampMs, strTimezone).format(STR_DISPLAY_DATETIME_FORMAT);
}

export function formatTimestampForDateTimeLocal(
  intTimestampMs: number,
  strTimezone: string,
): string {
  if (
    !Number.isSafeInteger(intTimestampMs) ||
    intTimestampMs < 0 ||
    !isValidTimezone(strTimezone)
  ) {
    return "";
  }

  return moment.tz(intTimestampMs, strTimezone).format(STR_DATETIME_LOCAL_FORMAT_SECOND);
}

export function parseDateTimeLocalToTimestamp(
  strDateTimeLocal: string,
  strTimezone: string,
): number | undefined {
  if (!isValidTimezone(strTimezone)) {
    return undefined;
  }

  const strFormat =
    strDateTimeLocal.length === STR_DATETIME_LOCAL_FORMAT_MINUTE.length
      ? STR_DATETIME_LOCAL_FORMAT_MINUTE
      : strDateTimeLocal.length === STR_DATETIME_LOCAL_FORMAT_SECOND.length
        ? STR_DATETIME_LOCAL_FORMAT_SECOND
        : undefined;
  if (strFormat === undefined) {
    return undefined;
  }

  const momentObj = moment.tz(strDateTimeLocal, strFormat, true, strTimezone);
  if (!momentObj.isValid() || momentObj.format(strFormat) !== strDateTimeLocal) {
    return undefined;
  }

  const intTimestampMs = momentObj.valueOf();
  return Number.isSafeInteger(intTimestampMs) && intTimestampMs >= 0
    ? intTimestampMs
    : undefined;
}

export function getDefaultSchedulePeriod(strTimezone: string): {
  strPeriodStartLocal: string;
  strPeriodEndLocal: string;
} {
  if (!isValidTimezone(strTimezone)) {
    throw new Error(`Invalid Executor time zone: ${strTimezone}`);
  }

  return {
    strPeriodStartLocal: moment
      .tz(strTimezone)
      .startOf("day")
      .format(STR_DATETIME_LOCAL_FORMAT_SECOND),
    strPeriodEndLocal: STR_DEFAULT_PERIOD_END_LOCAL,
  };
}
