// FileName: packagePublishing.ts

import { createHash } from "node:crypto";
import { open } from "node:fs/promises";

import { isRecord } from "../../Common/typeCheck";
import type { ConsolePublishDepartment } from "../../Domain/Console/consoleTypes";
import { requestConsole } from "./consoleClient";

const STR_PACKAGE_API = "/api/clients/editor/packages/";
const INT_MAX_PACKAGE_BYTES = 512 * 1024 * 1024;
const INT_MAX_CHUNK_BYTES = 4 * 1024 * 1024;

enum PackageUploadState {
  Receiving = "receiving",
  Completed = "completed",
  Failed = "failed",
  Expired = "expired",
  Canceled = "canceled",
}

interface PackageUploadInfo {
  upload_id: string;
  state: PackageUploadState;
  offset: number;
  size_bytes: number;
  chunk_bytes: number;
  package: { id: string } | null;
}

function parseUploadInfo(value: unknown): PackageUploadInfo {
  if (
    !isRecord(value) ||
    typeof value["upload_id"] !== "string" ||
    !/^[0-9a-f-]{36}$/i.test(value["upload_id"]) ||
    !Object.values(PackageUploadState).some((state) => state === value["state"]) ||
    typeof value["offset"] !== "number" ||
    !Number.isSafeInteger(value["offset"]) ||
    value["offset"] < 0 ||
    typeof value["size_bytes"] !== "number" ||
    !Number.isSafeInteger(value["size_bytes"]) ||
    value["size_bytes"] <= 0 ||
    value["offset"] > value["size_bytes"] ||
    typeof value["chunk_bytes"] !== "number" ||
    !Number.isSafeInteger(value["chunk_bytes"]) ||
    value["chunk_bytes"] <= 0 ||
    value["chunk_bytes"] > INT_MAX_CHUNK_BYTES ||
    !(
      value["package"] === null ||
      (isRecord(value["package"]) && typeof value["package"]["id"] === "string")
    )
  ) {
    throw new Error("Console returned an invalid Package upload response.");
  }
  return value as unknown as PackageUploadInfo;
}

export async function getConsolePackageDepartments(
  url: string,
  token: string,
): Promise<ConsolePublishDepartment[]> {
  const responseValue = await requestConsole(url, `${STR_PACKAGE_API}departments/`, token);
  if (
    !isRecord(responseValue) ||
    !Array.isArray(responseValue["departments"]) ||
    !responseValue["departments"].every(
      (entry: unknown) =>
        isRecord(entry) &&
        typeof entry["id"] === "string" &&
        typeof entry["name"] === "string" &&
        typeof entry["path"] === "string",
    )
  ) {
    throw new Error("Console returned invalid publishing departments.");
  }
  return responseValue["departments"] as ConsolePublishDepartment[];
}

export async function publishConsolePackage(
  url: string,
  token: string,
  packageFilePath: string,
  departmentId: string,
  requestId: string,
): Promise<string> {
  const fileObj = await open(packageFilePath, "r");
  try {
    const fileStat = await fileObj.stat();
    if (!fileStat.isFile() || fileStat.size <= 0 || fileStat.size > INT_MAX_PACKAGE_BYTES) {
      throw new Error("The Package must be a file no larger than 512 MiB.");
    }
    const hashObj = createHash("sha256");
    const chunkBuffer = Buffer.alloc(INT_MAX_CHUNK_BYTES);
    let intHashOffset = 0;
    while (intHashOffset < fileStat.size) {
      const { bytesRead: intBytesRead } = await fileObj.read(
        chunkBuffer,
        0,
        Math.min(chunkBuffer.length, fileStat.size - intHashOffset),
        intHashOffset,
      );
      if (intBytesRead === 0) {
        throw new Error("The Package file changed while preparing the upload.");
      }
      hashObj.update(chunkBuffer.subarray(0, intBytesRead));
      intHashOffset += intBytesRead;
    }
    let uploadInfo = parseUploadInfo(
      await requestConsole(url, `${STR_PACKAGE_API}uploads/`, token, {
        department_id: departmentId,
        request_id: requestId,
        size_bytes: fileStat.size,
        sha256: hashObj.digest("hex"),
      }),
    );
    if (uploadInfo.size_bytes !== fileStat.size) {
      throw new Error("Console returned an upload for a different Package size.");
    }
    const strUploadApi = `${STR_PACKAGE_API}uploads/${uploadInfo.upload_id}/`;
    while (
      uploadInfo.state === PackageUploadState.Receiving &&
      uploadInfo.offset < fileStat.size
    ) {
      const intOffset = uploadInfo.offset;
      const intChunkSize = Math.min(uploadInfo.chunk_bytes, fileStat.size - intOffset);
      const { bytesRead: intBytesRead } = await fileObj.read(
        chunkBuffer,
        0,
        intChunkSize,
        intOffset,
      );
      if (intBytesRead !== intChunkSize) {
        throw new Error("The Package file changed during the upload.");
      }
      const chunk = new Uint8Array(chunkBuffer.subarray(0, intBytesRead));
      uploadInfo = parseUploadInfo(
        await requestConsole(
          url,
          `${strUploadApi}chunks/${String(intOffset)}/`,
          token,
          chunk,
          {
            method: "PUT",
            headers: { "X-Chunk-SHA256": createHash("sha256").update(chunk).digest("hex") },
            timeoutMs: 120_000,
          },
        ),
      );
      if (uploadInfo.offset !== intOffset + intBytesRead) {
        throw new Error("Console returned an unexpected Package upload offset.");
      }
    }
    if (uploadInfo.state === PackageUploadState.Receiving) {
      uploadInfo = parseUploadInfo(
        await requestConsole(
          url,
          `${strUploadApi}complete/`,
          token,
          {},
          {
            timeoutMs: 120_000,
          },
        ),
      );
    }
    if (uploadInfo.state !== PackageUploadState.Completed || uploadInfo.package === null) {
      throw new Error(
        `The Package upload is ${uploadInfo.state}. Upload the local file from Console if this transfer can no longer be resumed.`,
      );
    }
    return uploadInfo.package.id;
  } finally {
    await fileObj.close();
  }
}
