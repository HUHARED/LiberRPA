// FileName: commonValue.ts

import moment from "moment-timezone";

import { isValidTimeZone } from "./dateTime";
import type { TypeColumns_LogLevel } from "../../shared/interface";

export const arrLogLevel: TypeColumns_LogLevel[] = [
  "VERBOSE",
  "DEBUG",
  "INFO",
  "WARNING",
  "ERROR",
  "CRITICAL",
];

export const arrTimezone = moment.tz.names().filter(isValidTimeZone);
