// FileName: files.ts

export async function getSha256(data: Blob | Uint8Array<ArrayBuffer>): Promise<string> {
  const bytes = data instanceof Blob ? await data.arrayBuffer() : data;
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
}

export function saveBlob(blob: Blob, name: string): void {
  const link = document.createElement("a");
  const strUrl = URL.createObjectURL(blob);
  link.href = strUrl;
  link.download = name;
  try {
    document.body.append(link);
    link.click();
  } finally {
    link.remove();
    // Leave enough time for the browser to accept the save request.
    setTimeout(() => URL.revokeObjectURL(strUrl), 60000);
  }
}
