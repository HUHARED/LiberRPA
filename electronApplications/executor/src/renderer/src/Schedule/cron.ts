import cronstrue from "cronstrue";

export type CronValidationResult =
  | {
      valid: true;
      description: string;
    }
  | {
      valid: false;
      error: string;
    };

export function validateCronExpression(cron: string): CronValidationResult {
  try {
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
      error: `Cron error: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
}
