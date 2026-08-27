// FileName: json.ts

export function cloneJsonSerializable<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}
