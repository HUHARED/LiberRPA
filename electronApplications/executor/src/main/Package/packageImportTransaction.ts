// FileName: packageImportTransaction.ts

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

interface Dict_PackageImport_Transaction {
  schemaVersion: 1;
  state: "prepared";
  projectName: string;
  projectVersion: string;
  targetFolderName: string;
}

interface Dict_PackageImport_StagingPaths {
  transactionFolderPath: string;
  stagedProjectPath: string;
}

const STR_STAGING_FOLDER_NAME = ".staging";
const STR_TRANSACTION_FILE_NAME = "transaction.json";
const STR_STAGED_PROJECT_FOLDER_NAME = "project";

function parseTransaction(transactionPath: string): Dict_PackageImport_Transaction {
  const dictTransaction = ensureExactRecord(
    readJsonFile(transactionPath, "Package import transaction"),
    ["schemaVersion", "state", "projectName", "projectVersion", "targetFolderName"],
    "Package import transaction",
  );
  if (dictTransaction.schemaVersion !== 1 || dictTransaction.state !== "prepared") {
    throw new Error(`Invalid Package import transaction: ${transactionPath}`);
  }

  const strProjectName = ensureNonEmptyString(
    dictTransaction.projectName,
    "Package import transaction.projectName",
  );
  const strProjectVersion = ensureNonEmptyString(
    dictTransaction.projectVersion,
    "Package import transaction.projectVersion",
  );
  const strTargetFolderName = ensureNonEmptyString(
    dictTransaction.targetFolderName,
    "Package import transaction.targetFolderName",
  );
  if (getTargetFolderName(strProjectName, strProjectVersion) !== strTargetFolderName) {
    throw new Error(
      `Package import transaction target is inconsistent: ${transactionPath}`,
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

export function removePackageImportFolderBestEffort(
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

export function createProjectPackageImportStaging(): Dict_PackageImport_StagingPaths {
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

export function writeProjectPackageImportTransaction({
  transactionFolderPath,
  projectName,
  projectVersion,
}: {
  transactionFolderPath: string;
  projectName: string;
  projectVersion: string;
}): void {
  const dictTransaction: Dict_PackageImport_Transaction = {
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

export function recoverProjectPackageImports(): void {
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
      removePackageImportFolderBestEffort(
        strTransactionFolderPath,
        "Failed to remove an invalid Package import staging entry",
      );
      continue;
    }

    const strTransactionPath = path.join(
      strTransactionFolderPath,
      STR_TRANSACTION_FILE_NAME,
    );
    if (!fs.existsSync(strTransactionPath)) {
      removePackageImportFolderBestEffort(
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
        loggerMain.warn(
          `Roll back an incomplete Package import: ${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
        );
        boolRecovered = removePackageImportFolderBestEffort(
          strTargetPath,
          "Failed to roll back an incomplete Package import",
        );
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
        `Failed to inspect Package import transaction ${strTransactionFolderPath}: ${getErrorMessage(e)}`,
      );
    }

    if (boolRecovered) {
      removePackageImportFolderBestEffort(
        strTransactionFolderPath,
        "Failed to clean a recovered Package import transaction",
      );
    } else {
      loggerMain.error(
        `Keep unresolved Package import transaction: ${strTransactionFolderPath}`,
      );
    }
  }
}
