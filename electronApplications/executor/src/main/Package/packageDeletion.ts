// FileName: packageDeletion.ts

import { randomUUID } from "crypto";
import fs from "fs";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import { readJsonFile, writeJsonFileAtomic } from "../Common/jsonFile";
import {
  ensureExactRecord,
  ensureNonEmptyString,
  ensurePositiveInteger,
} from "../Common/validation";
import {
  dbDeletePackage,
  dbSelectPackageBoundSchedules,
  dbSelectPackageDetailsById,
} from "../Database/packageRepository";
import { dbHasRunningRunForPackage } from "../Database/runHistoryRepository";
import {
  strLocalPackageRootPath,
  getLocalPackageFolderPath,
} from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import { isPackageRunStarting } from "../Run/packageRunner";
import { hasQueuedRunForPackage } from "../Scheduler/schedulerEngine";

interface PackageDeletionTransaction {
  schemaVersion: 1;
  packageId: number;
  projectName: string;
  projectVersion: string;
}

const STR_DELETE_STAGING_FOLDER_NAME = ".delete-staging";
const STR_TRANSACTION_FILE_NAME = "transaction.json";
const STR_STAGED_PACKAGE_FOLDER_NAME = "package";

function getDeleteStagingRootPath(): string {
  return path.join(strLocalPackageRootPath, STR_DELETE_STAGING_FOLDER_NAME);
}

function readPackageDeletionTransaction(
  transactionPath: string,
): PackageDeletionTransaction {
  const dictTransaction = ensureExactRecord(
    readJsonFile(transactionPath, "Package deletion transaction"),
    ["schemaVersion", "packageId", "projectName", "projectVersion"],
    "Package deletion transaction",
  );
  if (dictTransaction.schemaVersion !== 1) {
    throw new Error(`Unsupported Package deletion transaction: ${transactionPath}`);
  }

  const intPackageId = ensurePositiveInteger(
    dictTransaction.packageId,
    "Package deletion transaction.packageId",
  );
  const strProjectName = ensureNonEmptyString(
    dictTransaction.projectName,
    "Package deletion transaction.projectName",
  );
  const strProjectVersion = ensureNonEmptyString(
    dictTransaction.projectVersion,
    "Package deletion transaction.projectVersion",
  );

  return {
    schemaVersion: 1,
    packageId: intPackageId,
    projectName: strProjectName,
    projectVersion: strProjectVersion,
  };
}

async function removeFolderBestEffort(
  folderPath: string,
  context: string,
): Promise<boolean> {
  try {
    await fs.promises.rm(folderPath, { recursive: true, force: true });
    return true;
  } catch (e: unknown) {
    loggerMain.warn(`${context}: ${getErrorMessage(e)}`);
    return false;
  }
}

export async function deleteInstalledPackage(packageId: number): Promise<void> {
  const dictPackage = dbSelectPackageDetailsById(packageId);
  if (dictPackage === undefined) {
    throw new Error(`Package not found: ${packageId}`);
  }

  const arrBoundSchedule = dbSelectPackageBoundSchedules(packageId);
  if (arrBoundSchedule.length !== 0) {
    throw new Error(
      `Cannot delete Package ${packageId} because it is used by Schedule: ${arrBoundSchedule
        .map((dictSchedule) => dictSchedule.name)
        .join(", ")}.`,
    );
  }
  if (hasQueuedRunForPackage(packageId)) {
    throw new Error(
      `Cannot delete Package ${packageId} while it has a waiting Run or pending retry.`,
    );
  }
  if (isPackageRunStarting(packageId) || dbHasRunningRunForPackage(packageId)) {
    throw new Error(`Cannot delete Package ${packageId} while it is running.`);
  }

  const strTargetPath = getLocalPackageFolderPath(
    dictPackage.project_name,
    dictPackage.project_version,
  );
  if (!fs.existsSync(strTargetPath)) {
    loggerMain.warn(
      `Installed Package folder is already missing: ${dictPackage.project_name}-${dictPackage.project_version}`,
    );
    dbDeletePackage(packageId);
    return;
  }

  const strTransactionFolderPath = path.join(getDeleteStagingRootPath(), randomUUID());
  const strStagedPackagePath = path.join(
    strTransactionFolderPath,
    STR_STAGED_PACKAGE_FOLDER_NAME,
  );
  fs.mkdirSync(strTransactionFolderPath, { recursive: true });

  const dictTransaction: PackageDeletionTransaction = {
    schemaVersion: 1,
    packageId,
    projectName: dictPackage.project_name,
    projectVersion: dictPackage.project_version,
  };
  writeJsonFileAtomic(
    path.join(strTransactionFolderPath, STR_TRANSACTION_FILE_NAME),
    dictTransaction,
  );

  fs.renameSync(strTargetPath, strStagedPackagePath);
  try {
    dbDeletePackage(packageId);
  } catch (e: unknown) {
    let boolRestored = false;
    try {
      if (!fs.existsSync(strTargetPath) && fs.existsSync(strStagedPackagePath)) {
        fs.renameSync(strStagedPackagePath, strTargetPath);
      }
      boolRestored = fs.existsSync(strTargetPath);
    } catch (restoreError: unknown) {
      loggerMain.error(
        `Failed to restore Package folder after database deletion failure: ${getErrorMessage(restoreError)}`,
      );
    }

    if (boolRestored) {
      await removeFolderBestEffort(
        strTransactionFolderPath,
        "Failed to clean rolled-back Package deletion transaction",
      );
    } else {
      loggerMain.error(
        `Keep Package deletion transaction for recovery: ${strTransactionFolderPath}`,
      );
    }
    throw e;
  }

  await removeFolderBestEffort(
    strTransactionFolderPath,
    "Failed to clean completed Package deletion transaction",
  );
  loggerMain.info(
    `Deleted installed Package: ${dictPackage.project_name}-${dictPackage.project_version}`,
  );
}

export async function recoverPackageDeletions(): Promise<void> {
  const strStagingRootPath = getDeleteStagingRootPath();
  if (!fs.existsSync(strStagingRootPath)) {
    return;
  }

  for (const entryObj of fs.readdirSync(strStagingRootPath, { withFileTypes: true })) {
    const strTransactionFolderPath = path.join(strStagingRootPath, entryObj.name);
    if (!entryObj.isDirectory()) {
      await removeFolderBestEffort(
        strTransactionFolderPath,
        "Failed to remove invalid Package deletion staging entry",
      );
      continue;
    }

    const strTransactionPath = path.join(
      strTransactionFolderPath,
      STR_TRANSACTION_FILE_NAME,
    );
    if (!fs.existsSync(strTransactionPath)) {
      await removeFolderBestEffort(
        strTransactionFolderPath,
        "Failed to remove Package deletion staging folder without transaction",
      );
      continue;
    }

    let boolRecovered = false;
    try {
      const dictTransaction = readPackageDeletionTransaction(strTransactionPath);
      const dictPackage = dbSelectPackageDetailsById(dictTransaction.packageId);
      const strTargetPath = getLocalPackageFolderPath(
        dictTransaction.projectName,
        dictTransaction.projectVersion,
      );
      const strStagedPackagePath = path.join(
        strTransactionFolderPath,
        STR_STAGED_PACKAGE_FOLDER_NAME,
      );

      if (dictPackage === undefined) {
        // Database deletion completed. The staged copy belongs to the deleted installation.
        // Do not touch targetPath because the same Project version may have been installed again after the original deletion completed.
        boolRecovered = true;
      } else if (
        dictPackage.project_name !== dictTransaction.projectName ||
        dictPackage.project_version !== dictTransaction.projectVersion
      ) {
        loggerMain.error(
          `Package deletion transaction no longer matches database record ${dictTransaction.packageId}.`,
        );
      } else if (!fs.existsSync(strTargetPath) && fs.existsSync(strStagedPackagePath)) {
        loggerMain.warn(
          `Restore an incomplete Package deletion: ${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
        );
        fs.renameSync(strStagedPackagePath, strTargetPath);
        boolRecovered = true;
      } else if (fs.existsSync(strTargetPath) && fs.existsSync(strStagedPackagePath)) {
        loggerMain.warn(
          "Remove duplicate staged Package from deletion recovery: " +
            `${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
        );
        boolRecovered = await removeFolderBestEffort(
          strStagedPackagePath,
          "Failed to remove duplicate staged Package during deletion recovery",
        );
      } else if (fs.existsSync(strTargetPath)) {
        // The delete had not moved the installed folder yet.
        boolRecovered = true;
      } else {
        loggerMain.error(
          "Package folder is missing while recovering deletion: " +
            `${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
        );
      }
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to recover Package deletion transaction ${strTransactionFolderPath}: ${getErrorMessage(e)}`,
      );
    }

    if (boolRecovered) {
      await removeFolderBestEffort(
        strTransactionFolderPath,
        "Failed to clean recovered Package deletion transaction",
      );
    } else {
      loggerMain.error(
        `Keep unresolved Package deletion transaction: ${strTransactionFolderPath}`,
      );
    }
  }
}
