export function getProjectSourceColor(source: string): string {
  return source === "local" ? "info" : "teal";
}
