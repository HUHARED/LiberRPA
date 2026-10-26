// FileName: packageInstallationTransaction.ts

import { randomUUID } from "crypto";
import fs from "fs";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import { readJsonFile, writeJsonFileAtomic } from "../Common/jsonFile";
import { ensureExactRecord, ensureNonEmptyString } from "../Common/validation";
import { dbSelectPackageDetails } from "../Database/packageRepository";
import {
  strLocalPackageRootPath,
  getLocalPackageFolderPath,
} from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";

// NOTE: Recovery uses the filesystem and database state; this journal only identifies the installation.
interface PackageInstallationTransaction {
  schemaVersion: 1;
  projectName: string;
  projectVersion: string;
}

interface PackageInstallationStagingPaths {
  transactionFolderPath: string;
  stagedPackagePath: string;
}

const STR_STAGING_FOLDER_NAME = ".staging";
const STR_TRANSACTION_FILE_NAME = "transaction.json";
const STR_STAGED_PACKAGE_FOLDER_NAME = "package";

function readPackageInstallationTransaction(
  transactionPath: string,
): PackageInstallationTransaction {
  const dictTransaction = ensureExactRecord(
    readJsonFile(transactionPath, "Package installation transaction"),
    ["schemaVersion", "projectName", "projectVersion"],
    "Package installation transaction",
  );
  if (dictTransaction.schemaVersion !== 1) {
    throw new Error(`Invalid Package installation transaction: ${transactionPath}`);
  }

  const strProjectName = ensureNonEmptyString(
    dictTransaction.projectName,
    "Package installation transaction.projectName",
  );
  const strProjectVersion = ensureNonEmptyString(
    dictTransaction.projectVersion,
    "Package installation transaction.projectVersion",
  );

  return {
    schemaVersion: 1,
    projectName: strProjectName,
    projectVersion: strProjectVersion,
  };
}

export async function removePackageInstallationFolderBestEffort(
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

export function createPackageInstallationStaging(): PackageInstallationStagingPaths {
  fs.mkdirSync(strLocalPackageRootPath, { recursive: true });

  const strTransactionFolderPath = path.join(
    strLocalPackageRootPath,
    STR_STAGING_FOLDER_NAME,
    randomUUID(),
  );
  const strStagedPackagePath = path.join(
    strTransactionFolderPath,
    STR_STAGED_PACKAGE_FOLDER_NAME,
  );
  fs.mkdirSync(strStagedPackagePath, { recursive: true });

  return {
    transactionFolderPath: strTransactionFolderPath,
    stagedPackagePath: strStagedPackagePath,
  };
}

export function writePackageInstallationTransaction({
  transactionFolderPath,
  projectName,
  projectVersion,
}: {
  transactionFolderPath: string;
  projectName: string;
  projectVersion: string;
}): void {
  const dictTransaction: PackageInstallationTransaction = {
    schemaVersion: 1,
    projectName,
    projectVersion,
  };
  writeJsonFileAtomic(
    path.join(transactionFolderPath, STR_TRANSACTION_FILE_NAME),
    dictTransaction,
  );
}

export async function recoverPackageInstallations(): Promise<void> {
  const strStagingRootPath = path.join(strLocalPackageRootPath, STR_STAGING_FOLDER_NAME);
  if (!fs.existsSync(strStagingRootPath)) {
    return;
  }

  for (const entryObj of fs.readdirSync(strStagingRootPath, { withFileTypes: true })) {
    const strTransactionFolderPath = path.join(strStagingRootPath, entryObj.name);
    if (!entryObj.isDirectory()) {
      await removePackageInstallationFolderBestEffort(
        strTransactionFolderPath,
        "Failed to remove an invalid Package installation staging entry",
      );
      continue;
    }

    const strTransactionPath = path.join(
      strTransactionFolderPath,
      STR_TRANSACTION_FILE_NAME,
    );
    if (!fs.existsSync(strTransactionPath)) {
      await removePackageInstallationFolderBestEffort(
        strTransactionFolderPath,
        "Failed to remove a Package staging folder without a transaction",
      );
      continue;
    }

    let boolRecovered = false;
    try {
      const dictTransaction = readPackageInstallationTransaction(strTransactionPath);
      const strTargetPath = getLocalPackageFolderPath(
        dictTransaction.projectName,
        dictTransaction.projectVersion,
      );
      const boolTargetExists = fs.existsSync(strTargetPath);
      const packageRecord = dbSelectPackageDetails(
        dictTransaction.projectName,
        dictTransaction.projectVersion,
      );

      if (boolTargetExists && packageRecord === undefined) {
        const strStagedPackagePath = path.join(
          strTransactionFolderPath,
          STR_STAGED_PACKAGE_FOLDER_NAME,
        );
        if (fs.existsSync(strStagedPackagePath)) {
          // The atomic directory rename did not complete. Do not delete another target.
          loggerMain.warn(
            "Discard an incomplete Package installation with its staged Package still present; " +
              `leave the existing target unchanged: ${strTargetPath}`,
          );
          boolRecovered = true;
        } else {
          loggerMain.warn(
            "Roll back an incomplete Package installation: " +
              `${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
          );
          boolRecovered = await removePackageInstallationFolderBestEffort(
            strTargetPath,
            "Failed to roll back an incomplete Package installation",
          );
        }
      } else if (!boolTargetExists && packageRecord !== undefined) {
        loggerMain.error(
          "Installed Package folder is missing for database record: " +
            `${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
        );
      } else {
        // Both resources exist or neither exists, so the transaction is already consistent.
        boolRecovered = true;
      }
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to inspect Package installation transaction ${strTransactionFolderPath}: ${getErrorMessage(e)}`,
      );
    }

    if (boolRecovered) {
      await removePackageInstallationFolderBestEffort(
        strTransactionFolderPath,
        "Failed to clean a recovered Package installation transaction",
      );
    } else {
      loggerMain.error(
        `Keep unresolved Package installation transaction: ${strTransactionFolderPath}`,
      );
    }
  }
}
