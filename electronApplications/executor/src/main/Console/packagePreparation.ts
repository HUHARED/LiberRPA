// FileName: packagePreparation.ts

import { createHash, randomUUID } from "crypto";
import fs from "fs";
import path from "path";

import { ensureNonEmptyString, ensureRecord } from "../Common/validation";
import { getPythonEnvironmentPath, strDocumentsFolderPath } from "../Config/environment";
import { runFileWorker } from "../FileSystem/fileWorker";
import strPackageArchiveWorkerPath from "../Package/packageArchiveWorker?modulePath";
import type { PackageArchiveArgs } from "../Package/packageArchiveWorker";
import {
  readProjectPackageMetadata,
  validatePythonPackageEnvironment,
} from "../Package/packageMetadata";
import { requestConsole } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";

export interface ConsolePackageInfo {
  id: string;
  name: string;
  version: string;
  sha256: string;
}

const INT_MAX_PACKAGE_BYTES = 512 * 1024 ** 2;
const abortPreparation = new AbortController();
const mapPackageFilePreparation = new Map<string, Promise<void>>();

async function preparePackageFiles(
  packageInfo: ConsolePackageInfo,
  credential: ConsoleCredentialSnapshot,
  packagePath: string,
): Promise<void> {
  if (fs.existsSync(packagePath)) return;
  const strCacheRoot = path.dirname(packagePath);
  fs.mkdirSync(strCacheRoot, { recursive: true });
  const strStaging = path.join(strCacheRoot, `.staging-${randomUUID()}`);
  const strArchive = `${strStaging}.zip`;
  try {
    const response = await requestConsole(
      credential.consoleUrl,
      `executor/packages/${packageInfo.id}/downloads/`,
      credential.token,
      {},
    );
    const strTransferId = ensureNonEmptyString(
      response.transfer_id,
      "Package download transfer",
    );
    const metadata = ensureRecord(response.package, "Download package");
    if (metadata.sha256 !== packageInfo.sha256)
      throw new Error("Package digest changed during preparation.");
    const download = await fetch(
      `${credential.consoleUrl}/api/clients/executor/packages/downloads/${encodeURIComponent(strTransferId)}/content/`,
      {
        headers: { Authorization: `Bearer ${credential.token}` },
        redirect: "error",
        credentials: "omit",
        signal: AbortSignal.any([AbortSignal.timeout(120_000), abortPreparation.signal]),
      },
    );
    if (!download.ok || !download.body)
      throw new Error(`Package download failed (${download.status}).`);
    const digest = createHash("sha256");
    const fileObj = await fs.promises.open(strArchive, "wx");
    let intBytes = 0;
    try {
      for await (const chunk of download.body) {
        intBytes += chunk.byteLength;
        if (intBytes > INT_MAX_PACKAGE_BYTES)
          throw new Error("Package download exceeds 512 MiB.");
        abortPreparation.signal.throwIfAborted();
        digest.update(chunk);
        let intOffset = 0;
        while (intOffset < chunk.byteLength) {
          const { bytesWritten } = await fileObj.write(chunk, intOffset);
          if (bytesWritten === 0)
            throw new Error("The package download could not be written.");
          intOffset += bytesWritten;
        }
      }
    } finally {
      await fileObj.close();
    }
    if (intBytes !== metadata.size_bytes || digest.digest("hex") !== packageInfo.sha256)
      throw new Error("Downloaded package size or SHA256 does not match Console.");
    await runFileWorker<PackageArchiveArgs>(
      strPackageArchiveWorkerPath,
      { packageFilePath: strArchive, stagedProjectPath: strStaging },
      abortPreparation.signal,
    );
    abortPreparation.signal.throwIfAborted();
    const packageMetadata = await readProjectPackageMetadata(strStaging);
    if (
      packageMetadata.name !== packageInfo.name ||
      packageMetadata.version !== packageInfo.version
    )
      throw new Error("Package identity does not match the requested version.");
    abortPreparation.signal.throwIfAborted();
    fs.renameSync(strStaging, packagePath);
  } finally {
    try {
      await fs.promises.rm(strArchive, { force: true });
    } finally {
      await fs.promises.rm(strStaging, { force: true, recursive: true });
    }
  }
}

export async function prepareConsolePackage(
  packageInfo: ConsolePackageInfo,
  environmentName: string,
  credential: ConsoleCredentialSnapshot,
): Promise<string> {
  abortPreparation.signal.throwIfAborted();
  if (
    !/^[a-f0-9]{64}$/.test(packageInfo.sha256) ||
    !/^[a-f0-9-]{36}$/i.test(packageInfo.id)
  )
    throw new Error("Console package identity is invalid.");
  const strOriginHash = createHash("sha256").update(credential.consoleUrl).digest("hex");
  const strPackagePath = path.join(
    strDocumentsFolderPath,
    "LiberRPA/ConsolePackage",
    strOriginHash,
    packageInfo.id,
    packageInfo.sha256,
  );
  let promiseFiles = mapPackageFilePreparation.get(strPackagePath);
  if (promiseFiles === undefined) {
    // Share file work by its destination, not by the environment that will run it.
    promiseFiles = preparePackageFiles(packageInfo, credential, strPackagePath).finally(
      () => {
        mapPackageFilePreparation.delete(strPackagePath);
      },
    );
    mapPackageFilePreparation.set(strPackagePath, promiseFiles);
  }
  await promiseFiles;
  abortPreparation.signal.throwIfAborted();
  await validatePythonPackageEnvironment(
    strPackagePath,
    getPythonEnvironmentPath(environmentName),
  );
  return strPackagePath;
}

export function stopPackagePreparation(): void {
  abortPreparation.abort();
}
