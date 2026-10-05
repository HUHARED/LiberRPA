// FileName: cron.ts

import {
  CronExpressionParser,
  type CronExpression,
  type CronExpressionOptions,
} from "cron-parser";
import { isSupportedIntlTimezone } from "./timezone";

export function parseScheduleCron(
  cron: string,
  timezone: string,
  options: CronExpressionOptions = {},
): CronExpression {
  const arrField = cron.trim().split(/\s+/);
  if (
    ![5, 6].includes(arrField.length) ||
    arrField.some((strField) => !/^[0-9*,/-]+$/.test(strField))
  ) {
    throw new Error(
      "Use five fields, or six with seconds first; supported syntax: numbers, *, ranges, lists and steps.",
    );
  }
  if (!isSupportedIntlTimezone(timezone)) throw new Error("Select a valid IANA time zone.");
  return CronExpressionParser.parse(arrField.join(" "), { ...options, tz: timezone });
}

export function nextScheduleDate(
  interval: CronExpression,
): ReturnType<CronExpression["next"]> {
  while (true) {
    const date = interval.next();
    // cron-parser shifts nonexistent spring times forward; skip those wall times instead.
    if (
      interval.fields.hour.values.some((intHour) => intHour === date.getHours()) &&
      interval.fields.minute.values.some((intMinute) => intMinute === date.getMinutes()) &&
      interval.fields.second.values.some((intSecond) => intSecond === date.getSeconds())
    )
      return date;
  }
}

export function previewScheduleCron(
  cron: string,
  timezone: string,
  startMs: number,
  endMs: number,
): number[] {
  const arrTimestamp: number[] = [];
  try {
    const intervalObj = parseScheduleCron(cron, timezone, {
      currentDate: new Date(startMs),
      endDate: new Date(endMs),
    });
    for (let intIndex = 0; intIndex < 5 && intervalObj.hasNext(); intIndex++) {
      arrTimestamp.push(nextScheduleDate(intervalObj).toDate().getTime());
    }
  } catch {
    // A valid configuration may have no future trigger in its active period.
  }
  return arrTimestamp;
}
