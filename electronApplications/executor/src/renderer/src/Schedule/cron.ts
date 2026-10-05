// FileName: cron.ts

import cronstrue from "cronstrue";

import { getErrorMessage } from "../../../shared/error";
import { parseScheduleCron } from "../../../shared/cron";

type Dict_Result_CronValidation =
  | {
      valid: true;
      description: string;
    }
  | {
      valid: false;
      error: string;
    };

export function validateCronExpression(
  cron: string,
  timezone = "UTC",
): Dict_Result_CronValidation {
  try {
    parseScheduleCron(cron, timezone);
    return {
      valid: true,
      description: cronstrue.toString(cron, {
        use24HourTimeFormat: true,
        throwExceptionOnParseError: true,
        verbose: true,
      }),
    };
  } catch (e: unknown) {
    return {
      valid: false,
      error: `Cron error: ${getErrorMessage(e)}`,
    };
  }
}
