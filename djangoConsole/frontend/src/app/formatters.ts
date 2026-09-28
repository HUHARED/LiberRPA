// FileName: formatters.ts

export function getDisplayName(username: string, email: string): string {
  return username || email;
}

export function formatDateTime(value: string | null, timeZone: string): string {
  if (value === null) return "—";
  const dateValue = new Date(value);
  if (!Number.isFinite(dateValue.getTime())) return "Unknown";
  const arrPart = new Intl.DateTimeFormat("en", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
    timeZoneName: "longOffset",
  }).formatToParts(dateValue);
  const mapPart = new Map(arrPart.map((part) => [part.type, part.value]));
  // Intl uses "GMT" for a zero offset and "GMT±HH:mm" for other offsets.
  const strOffset = mapPart.get("timeZoneName")?.replace("GMT", "") || "+00:00";
  const strDate = `${mapPart.get("year")}-${mapPart.get("month")}-${mapPart.get("day")}`;
  const strTime = `${mapPart.get("hour")}:${mapPart.get("minute")}:${mapPart.get("second")}`;
  return `${strDate} ${strTime} ${strOffset}`;
}

export function formatDateTimeInput(value: string, timeZone: string): string {
  const arrPart = new Intl.DateTimeFormat("en", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(value));
  const mapPart = new Map(arrPart.map((part) => [part.type, part.value]));
  return `${mapPart.get("year")}-${mapPart.get("month")}-${mapPart.get("day")}T${mapPart.get("hour")}:${mapPart.get("minute")}`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GiB`;
}
