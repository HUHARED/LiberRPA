// FileName: packageInstallationTransaction.ts

import { randomUUID } from "crypto";
import fs from "fs";
import path from "path";

import { getErrorMessage } from "../../shared/error";
import { readJsonFile, writeJsonFileAtomic } from "../Common/jsonFile";
import { ensureExactRecord, ensureNonEmptyString } from "../Common/validation";
import { dbSelectProjectDetail } from "../Database/projectRepository";
import { strExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import { getTargetFolderName } from "./packageArchive";

interface Dict_PackageInstallation_Transaction {
  schemaVersion: 1;
  state: "prepared";
  projectName: string;
  projectVersion: string;
  targetFolderName: string;
}

interface Dict_PackageInstallation_StagingPaths {
  transactionFolderPath: string;
  stagedProjectPath: string;
}

const STR_STAGING_FOLDER_NAME = ".staging";
const STR_TRANSACTION_FILE_NAME = "transaction.json";
const STR_STAGED_PROJECT_FOLDER_NAME = "project";

function parseTransaction(transactionPath: string): Dict_PackageInstallation_Transaction {
  const dictTransaction = ensureExactRecord(
    readJsonFile(transactionPath, "Package installation transaction"),
    ["schemaVersion", "state", "projectName", "projectVersion", "targetFolderName"],
    "Package installation transaction",
  );
  if (dictTransaction.schemaVersion !== 1 || dictTransaction.state !== "prepared") {
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
  const strTargetFolderName = ensureNonEmptyString(
    dictTransaction.targetFolderName,
    "Package installation transaction.targetFolderName",
  );
  if (getTargetFolderName(strProjectName, strProjectVersion) !== strTargetFolderName) {
    throw new Error(
      `Package installation transaction target is inconsistent: ${transactionPath}`,
    );
  }

  return {
    schemaVersion: 1,
    state: "prepared",
    projectName: strProjectName,
    projectVersion: strProjectVersion,
    targetFolderName: strTargetFolderName,
  };
}

export function removePackageInstallationFolderBestEffort(
  folderPath: string,
  context: string,
): boolean {
  try {
    fs.rmSync(folderPath, { recursive: true, force: true });
    return true;
  } catch (e: unknown) {
    loggerMain.warn(`${context}: ${getErrorMessage(e)}`);
    return false;
  }
}

export function createProjectPackageInstallationStaging(): Dict_PackageInstallation_StagingPaths {
  fs.mkdirSync(strExecutorPackageFolderPath, { recursive: true });

  const strTransactionFolderPath = path.join(
    strExecutorPackageFolderPath,
    STR_STAGING_FOLDER_NAME,
    randomUUID(),
  );
  const strStagedProjectPath = path.join(
    strTransactionFolderPath,
    STR_STAGED_PROJECT_FOLDER_NAME,
  );
  fs.mkdirSync(strStagedProjectPath, { recursive: true });

  return {
    transactionFolderPath: strTransactionFolderPath,
    stagedProjectPath: strStagedProjectPath,
  };
}

export function writeProjectPackageInstallationTransaction({
  transactionFolderPath,
  projectName,
  projectVersion,
}: {
  transactionFolderPath: string;
  projectName: string;
  projectVersion: string;
}): void {
  const dictTransaction: Dict_PackageInstallation_Transaction = {
    schemaVersion: 1,
    state: "prepared",
    projectName,
    projectVersion,
    targetFolderName: getTargetFolderName(projectName, projectVersion),
  };
  writeJsonFileAtomic(
    path.join(transactionFolderPath, STR_TRANSACTION_FILE_NAME),
    dictTransaction,
  );
}

export function recoverProjectPackageInstallations(): void {
  const strStagingRootPath = path.join(
    strExecutorPackageFolderPath,
    STR_STAGING_FOLDER_NAME,
  );
  if (!fs.existsSync(strStagingRootPath)) {
    return;
  }

  for (const entryObj of fs.readdirSync(strStagingRootPath, { withFileTypes: true })) {
    const strTransactionFolderPath = path.join(strStagingRootPath, entryObj.name);
    if (!entryObj.isDirectory()) {
      removePackageInstallationFolderBestEffort(
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
      removePackageInstallationFolderBestEffort(
        strTransactionFolderPath,
        "Failed to remove a Package staging folder without a transaction",
      );
      continue;
    }

    let boolRecovered = false;
    try {
      const dictTransaction = parseTransaction(strTransactionPath);
      const strTargetPath = path.join(
        strExecutorPackageFolderPath,
        dictTransaction.targetFolderName,
      );
      const boolTargetExists = fs.existsSync(strTargetPath);
      const projectRecord = dbSelectProjectDetail(
        dictTransaction.projectName,
        dictTransaction.projectVersion,
      );

      if (boolTargetExists && projectRecord === undefined) {
        const strStagedProjectPath = path.join(
          strTransactionFolderPath,
          STR_STAGED_PROJECT_FOLDER_NAME,
        );
        if (fs.existsSync(strStagedProjectPath)) {
          // The atomic directory rename did not complete. Do not delete another target.
          loggerMain.warn(
            "Discard an incomplete Package installation with its staged project still present; " +
              `leave the existing target unchanged: ${strTargetPath}`,
          );
          boolRecovered = true;
        } else {
          loggerMain.warn(
            "Roll back an incomplete Package installation: " +
              `${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
          );
          boolRecovered = removePackageInstallationFolderBestEffort(
            strTargetPath,
            "Failed to roll back an incomplete Package installation",
          );
        }
      } else if (!boolTargetExists && projectRecord !== undefined) {
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
      removePackageInstallationFolderBestEffort(
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
