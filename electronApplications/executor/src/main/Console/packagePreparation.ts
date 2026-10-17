// FileName: packagePreparation.ts

import { createHash, randomUUID } from "crypto";
import fs from "fs";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import { ensureNonEmptyString, ensureRecord } from "../Common/validation";
import { getPythonEnvironmentPath } from "../Config/environment";
import { strConsolePackageFolderPath } from "../FileSystem/executorFiles";
import { runFileWorker } from "../FileSystem/fileWorker";
import { loggerMain } from "../Logging/logger";
import { getPackageFolderName } from "../Package/packageArchive";
import strPackageArchiveWorkerPath from "../Package/packageArchiveWorker?modulePath";
import type { PackageArchiveArgs } from "../Package/packageArchiveWorker";
import {
  readPackageMetadata,
  validatePackageLiberrpaRequirement,
} from "../Package/packageMetadata";
import { dbSelectConsolePackageId, dbSaveConsolePackage } from "./packageRepository";
import { requestConsole } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";

export interface ConsolePackageInfo {
  packageId: string;
  projectName: string;
  projectVersion: string;
  sha256: string;
}

const INT_MAX_PACKAGE_BYTES = 512 * 1024 ** 2; // 512 MiB.
const INT_PACKAGE_DOWNLOAD_IDLE_MS = 60_000;
const INT_PACKAGE_DOWNLOAD_TIMEOUT_MS = 30 * 60 * 1000;
const abortPreparation = new AbortController();
const mapPackageFilePreparation = new Map<
  string,
  { packageId: string; promise: Promise<void> }
>();

export async function cleanConsolePackageStaging(): Promise<void> {
  async function readEntries(folderPath: string): Promise<fs.Dirent[]> {
    try {
      // Do not traverse a linked Package root.
      if (!(await fs.promises.lstat(folderPath)).isDirectory()) return [];
      return await fs.promises.readdir(folderPath, { withFileTypes: true });
    } catch (e: unknown) {
      if (!(e instanceof Error && "code" in e && e.code === "ENOENT"))
        loggerMain.warn(
          `Failed to inspect Console package staging ${folderPath}: ${getErrorMessage(e)}`,
        );
      return [];
    }
  }

  // Called before any new preparation; ready Package directories are never traversed.
  let intRemoved = 0;
  for (const stagingEntry of await readEntries(strConsolePackageFolderPath)) {
    if (
      (!stagingEntry.isDirectory() && !stagingEntry.isFile()) ||
      !/^\.staging-[a-f0-9-]{36}(?:\.zip)?$/.test(stagingEntry.name)
    )
      continue;
    const strStagingPath = path.join(strConsolePackageFolderPath, stagingEntry.name);
    try {
      await fs.promises.rm(strStagingPath, { recursive: true, force: true });
      intRemoved += 1;
    } catch (e: unknown) {
      loggerMain.warn(
        `Failed to remove Console Package staging ${strStagingPath}: ${getErrorMessage(e)}`,
      );
    }
  }
  if (intRemoved)
    loggerMain.info(`Removed ${intRemoved} abandoned Console package staging entries.`);
}

async function preparePackageFiles(
  packageInfo: ConsolePackageInfo,
  credential: ConsoleCredentialSnapshot,
  packagePath: string,
): Promise<void> {
  const strFolderName = path.basename(packagePath);
  if (fs.existsSync(packagePath)) {
    if (
      dbSelectConsolePackageId(strFolderName) !== packageInfo.packageId ||
      !fs.statSync(packagePath).isDirectory()
    )
      throw new Error(`The target Console Package folder already exists: ${packagePath}`);
    // NOTE: A ready Package is a mutable working directory; do not hash or restore its files.
    return;
  }
  if (!/^[a-f0-9]{64}$/.test(packageInfo.sha256))
    throw new Error("Console Package SHA256 is invalid.");
  fs.mkdirSync(strConsolePackageFolderPath, { recursive: true });
  const strStaging = path.join(strConsolePackageFolderPath, `.staging-${randomUUID()}`);
  const strArchive = `${strStaging}.zip`;
  try {
    const response = await requestConsole(
      credential.consoleUrl,
      `executor/packages/${packageInfo.packageId}/downloads/`,
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
    const abortDownload = new AbortController();
    const signalDownload = AbortSignal.any([
      abortDownload.signal,
      AbortSignal.timeout(INT_PACKAGE_DOWNLOAD_TIMEOUT_MS),
      abortPreparation.signal,
    ]);
    let timerProgress: NodeJS.Timeout | undefined;
    function markDownloadProgress(): void {
      clearTimeout(timerProgress);
      timerProgress = setTimeout(() => {
        abortDownload.abort(new Error("Package download stopped making progress."));
      }, INT_PACKAGE_DOWNLOAD_IDLE_MS);
    }
    markDownloadProgress();
    try {
      const download = await fetch(
        `${credential.consoleUrl}/api/clients/executor/packages/downloads/${encodeURIComponent(strTransferId)}/content/`,
        {
          headers: { Authorization: `Bearer ${credential.token}` },
          redirect: "error",
          credentials: "omit",
          signal: signalDownload,
        },
      );
      if (!download.ok || !download.body)
        throw new Error(`Package download failed (${download.status}).`);
      markDownloadProgress();
      const digest = createHash("sha256");
      const fileObj = await fs.promises.open(strArchive, "wx");
      let intBytes = 0;
      try {
        for await (const chunk of download.body) {
          intBytes += chunk.byteLength;
          if (intBytes > INT_MAX_PACKAGE_BYTES)
            throw new Error("Package download exceeds 512 MiB.");
          signalDownload.throwIfAborted();
          digest.update(chunk);
          let intOffset = 0;
          while (intOffset < chunk.byteLength) {
            const { bytesWritten } = await fileObj.write(chunk, intOffset);
            if (bytesWritten === 0)
              throw new Error("The package download could not be written.");
            intOffset += bytesWritten;
            markDownloadProgress();
          }
        }
      } finally {
        await fileObj.close();
      }
      signalDownload.throwIfAborted();
      if (intBytes !== metadata.size_bytes || digest.digest("hex") !== packageInfo.sha256)
        throw new Error("Downloaded package size or SHA256 does not match Console.");
    } finally {
      clearTimeout(timerProgress);
      abortDownload.abort();
    }
    await runFileWorker<PackageArchiveArgs>(
      strPackageArchiveWorkerPath,
      { packageFilePath: strArchive, stagedPackagePath: strStaging },
      abortPreparation.signal,
    );
    abortPreparation.signal.throwIfAborted();
    const packageMetadata = await readPackageMetadata(strStaging);
    if (
      packageMetadata.project_name !== packageInfo.projectName ||
      packageMetadata.project_version !== packageInfo.projectVersion
    )
      throw new Error("Package identity does not match the requested version.");
    abortPreparation.signal.throwIfAborted();
    if (fs.existsSync(packagePath))
      throw new Error(`The target Console Package folder already exists: ${packagePath}`);
    fs.renameSync(strStaging, packagePath);
    try {
      // Keep the final rename and registration in the same synchronous turn.
      dbSaveConsolePackage(strFolderName, packageInfo.packageId);
    } catch (e: unknown) {
      fs.rmSync(packagePath, { recursive: true, force: true });
      throw e;
    }
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
  if (!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(packageInfo.packageId))
    throw new Error("Console Package ID is invalid.");
  const strPackagePath = path.join(
    strConsolePackageFolderPath,
    getPackageFolderName(packageInfo.projectName, packageInfo.projectVersion),
  );
  const strPreparationKey = strPackagePath.toLowerCase();
  let preparation = mapPackageFilePreparation.get(strPreparationKey);
  if (preparation && preparation.packageId !== packageInfo.packageId)
    throw new Error(
      `Another Console Package is being prepared in this folder: ${strPackagePath}`,
    );
  if (preparation === undefined) {
    // Share file work for the same Package, independently of its requested Python environment.
    preparation = {
      packageId: packageInfo.packageId,
      promise: preparePackageFiles(packageInfo, credential, strPackagePath).finally(() => {
        mapPackageFilePreparation.delete(strPreparationKey);
      }),
    };
    mapPackageFilePreparation.set(strPreparationKey, preparation);
  }
  await preparation.promise;
  abortPreparation.signal.throwIfAborted();
  await validatePackageLiberrpaRequirement(
    strPackagePath,
    getPythonEnvironmentPath(environmentName),
  );
  return strPackagePath;
}

export function stopPackagePreparation(): void {
  abortPreparation.abort();
}
