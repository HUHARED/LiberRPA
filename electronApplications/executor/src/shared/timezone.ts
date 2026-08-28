// FileName: timezone.ts

export function isSupportedIntlTimezone(timezone: string): boolean {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: timezone }).format();
    return true;
  } catch {
    return false;
  }
}

export function getSystemIntlTimezone(): string {
  const strTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  return strTimezone !== "" && isSupportedIntlTimezone(strTimezone) ? strTimezone : "UTC";
}
