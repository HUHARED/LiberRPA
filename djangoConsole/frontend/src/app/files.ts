// FileName: files.ts

export async function getSha256(data: Blob | Uint8Array<ArrayBuffer>): Promise<string> {
  const bytes = data instanceof Blob ? await data.arrayBuffer() : data;
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
}

export function downloadFile(path: string, name = ""): void {
  const link = document.createElement("a");
  link.href = path;
  link.download = name;
  link.click();
}
