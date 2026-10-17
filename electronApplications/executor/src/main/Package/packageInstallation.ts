// FileName: packageInstallation.ts

import { dialog } from "electron";
import fs from "fs";
import path from "path";
import { setTimeout as delay } from "timers/promises";

import { getErrorMessage } from "../../shared/error";
import {
  dbInsertPackageDetails,
  dbSelectPackageDetails,
} from "../Database/packageRepository";
import { runFileWorker } from "../FileSystem/fileWorker";
import { getLocalPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import type { PackageInstallResult } from "../../shared/package";
import strPackageArchiveWorkerPath from "./packageArchiveWorker?modulePath";
import type { PackageArchiveArgs } from "./packageArchiveWorker";
import {
  createPackageInstallationStaging,
  removePackageInstallationFolderBestEffort,
  writePackageInstallationTransaction,
} from "./packageInstallationTransaction";
import { readPackageMetadata } from "./packageMetadata";

// Bound retries for potentially temporary Windows access/sharing failures (4 seconds total).
const ARR_PACKAGE_RENAME_RETRY_DELAY_MS: readonly number[] = [
  100, 200, 400, 800, 1000, 1500,
];
const SET_PACKAGE_RENAME_RETRY_ERROR_CODE = new Set(["EPERM", "EBUSY", "EACCES"]);

let boolPackageSelectionOpen = false;
let promisePackageInstallation: Promise<PackageInstallResult> | undefined;
let strLastPackageFolderPath: string | undefined;

async function runPackageInstallation(
  packageFilePath: string,
  ensureExecutorRunning: () => void,
): Promise<PackageInstallResult> {
  const { transactionFolderPath, stagedPackagePath } = createPackageInstallationStaging();

  let strTargetPath: string | undefined;
  let boolTransactionWritten = false;
  let boolTargetRenamed = false;
  let boolDatabaseCommitted = false;
  try {
    await runFileWorker<PackageArchiveArgs>(strPackageArchiveWorkerPath, {
      packageFilePath,
      stagedPackagePath,
    });
    ensureExecutorRunning();
    const packageMetadata = await readPackageMetadata(stagedPackagePath);
    ensureExecutorRunning();

    if (
      dbSelectPackageDetails(
        packageMetadata.project_name,
        packageMetadata.project_version,
      ) !== undefined
    ) {
      throw new Error(
        `Package ${packageMetadata.project_name}-${packageMetadata.project_version} is already installed.`,
      );
    }

    strTargetPath = getLocalPackageFolderPath(
      packageMetadata.project_name,
      packageMetadata.project_version,
    );
    if (fs.existsSync(strTargetPath)) {
      throw new Error(`The target Package folder already exists: ${strTargetPath}`);
    }

    writePackageInstallationTransaction({
      transactionFolderPath,
      projectName: packageMetadata.project_name,
      projectVersion: packageMetadata.project_version,
    });
    boolTransactionWritten = true;

    let intRenameRetryCount = 0;
    while (true) {
      try {
        fs.renameSync(stagedPackagePath, strTargetPath);
        boolTargetRenamed = true;
        break;
      } catch (e: unknown) {
        const strErrorCode =
          typeof e === "object" && e !== null && "code" in e && typeof e.code === "string"
            ? e.code
            : undefined;
        if (
          process.platform !== "win32" ||
          strErrorCode === undefined ||
          !SET_PACKAGE_RENAME_RETRY_ERROR_CODE.has(strErrorCode)
        ) {
          throw e;
        }

        const intRetryDelayMs = ARR_PACKAGE_RENAME_RETRY_DELAY_MS[intRenameRetryCount];
        if (intRetryDelayMs === undefined) {
          throw new Error(
            `Could not move the staged Package after ${intRenameRetryCount + 1} attempts. ` +
              "The folder may still be in use or access may be denied. " +
              getErrorMessage(e),
            { cause: e },
          );
        }

        intRenameRetryCount += 1;
        loggerMain.warn(
          `Package folder rename failed with ${strErrorCode}; ` +
            `retry ${intRenameRetryCount}/${ARR_PACKAGE_RENAME_RETRY_DELAY_MS.length} ` +
            `in ${intRetryDelayMs} ms: ${stagedPackagePath} -> ${strTargetPath}`,
        );
        // Wait without blocking Main. No target folder has been committed at this point.
        await delay(intRetryDelayMs);
        ensureExecutorRunning();
        if (fs.existsSync(strTargetPath)) {
          throw new Error(`The target Package folder already exists: ${strTargetPath}`);
        }
      }
    }

    // Keep the successful rename and database commit in the same synchronous turn.
    dbInsertPackageDetails(packageMetadata);
    boolDatabaseCommitted = true;

    if (intRenameRetryCount > 0) {
      loggerMain.info(
        `Package folder rename succeeded (retries: ${intRenameRetryCount}): ${strTargetPath}`,
      );
    }

    await removePackageInstallationFolderBestEffort(
      transactionFolderPath,
      "Failed to clean the completed Package installation transaction",
    );
    loggerMain.info(
      `Installed Flow Package: ${packageMetadata.project_name}-${packageMetadata.project_version}`,
    );
    return {
      status: "packageInstalled",
      project_name: packageMetadata.project_name,
      project_version: packageMetadata.project_version,
    };
  } catch (e: unknown) {
    let boolRollbackComplete = !boolTransactionWritten;

    if (boolTransactionWritten && !boolDatabaseCommitted) {
      // A target that appeared while waiting was not created by this installation.
      if (
        !boolTargetRenamed ||
        strTargetPath === undefined ||
        !fs.existsSync(strTargetPath)
      ) {
        boolRollbackComplete = true;
      } else {
        boolRollbackComplete = await removePackageInstallationFolderBestEffort(
          strTargetPath,
          "Failed to roll back the installed Package folder",
        );
      }
    }

    if (boolRollbackComplete) {
      await removePackageInstallationFolderBestEffort(
        transactionFolderPath,
        "Failed to clean the failed Package installation transaction",
      );
    } else {
      loggerMain.error(
        `Keep unresolved Package installation transaction: ${transactionFolderPath}`,
      );
    }
    throw e;
  }
}

export async function installPackage(
  ensureExecutorRunning: () => void,
): Promise<PackageInstallResult> {
  if (boolPackageSelectionOpen || promisePackageInstallation !== undefined) {
    throw new Error("Another Package installation is already running.");
  }

  boolPackageSelectionOpen = true;
  try {
    const dialogResult = await dialog.showOpenDialog({
      defaultPath: strLastPackageFolderPath,
      properties: ["openFile"],
      title: "Select a Flow Package",
      filters: [{ name: "LiberRPA Flow Package", extensions: ["rpa.zip"] }],
    });
    boolPackageSelectionOpen = false;
    if (dialogResult.canceled) return { status: "canceled" };
    // Shutdown may have started while the native file dialog was open.
    ensureExecutorRunning();
    if (dialogResult.filePaths.length !== 1) {
      throw new Error("Exactly one Flow Package must be selected.");
    }

    const strPackageFilePath = dialogResult.filePaths[0];
    strLastPackageFolderPath = path.dirname(strPackageFilePath);
    promisePackageInstallation = runPackageInstallation(
      strPackageFilePath,
      ensureExecutorRunning,
    );
    return await promisePackageInstallation;
  } finally {
    boolPackageSelectionOpen = false;
    promisePackageInstallation = undefined;
  }
}

export async function waitForPackageInstallation(): Promise<void> {
  await promisePackageInstallation?.catch(() => {});
}
