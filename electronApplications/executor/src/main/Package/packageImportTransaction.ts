// FileName: packageImportTransaction.ts

import { randomUUID } from "crypto";
import fs from "fs";
import path from "path";

import { ensureExactRecord, ensureString } from "../Common/validation";
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

function readJsonFile(filePath: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(filePath, { encoding: "utf-8" }));
  } catch (e: unknown) {
    throw new Error(`Failed to read JSON file: ${filePath}`, { cause: e });
  }
}

function writeJsonFileAtomic(filePath: string, value: unknown): void {
  const strTempPath = `${filePath}.tmp`;
  fs.rmSync(strTempPath, { force: true });
  fs.writeFileSync(strTempPath, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: "utf-8",
  });
  fs.renameSync(strTempPath, filePath);
}

function parseTransaction(transactionPath: string): Dict_PackageImport_Transaction {
  const dictTransaction = ensureExactRecord(
    readJsonFile(transactionPath),
    ["schemaVersion", "state", "projectName", "projectVersion", "targetFolderName"],
    "Package import transaction",
  );
  if (dictTransaction.schemaVersion !== 1 || dictTransaction.state !== "prepared") {
    throw new Error(`Invalid Package import transaction: ${transactionPath}`);
  }

  const strProjectName = ensureString(
    dictTransaction.projectName,
    "Package import transaction.projectName",
  );
  const strProjectVersion = ensureString(
    dictTransaction.projectVersion,
    "Package import transaction.projectVersion",
  );
  const strTargetFolderName = ensureString(
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

function removeFolder(strFolderPath: string): void {
  fs.rmSync(strFolderPath, { recursive: true, force: true });
}

export function tryRemovePackageImportFolder(folderPath: string, context: string): void {
  try {
    removeFolder(folderPath);
  } catch (e: unknown) {
    loggerMain.warn(`${context}: ${e instanceof Error ? e.message : String(e)}`);
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
  targetFolderName,
}: {
  transactionFolderPath: string;
  projectName: string;
  projectVersion: string;
  targetFolderName: string;
}): void {
  if (getTargetFolderName(projectName, projectVersion) !== targetFolderName) {
    throw new Error("Package import transaction target is inconsistent.");
  }

  const transactionDict: Dict_PackageImport_Transaction = {
    schemaVersion: 1,
    state: "prepared",
    projectName,
    projectVersion,
    targetFolderName,
  };
  writeJsonFileAtomic(
    path.join(transactionFolderPath, STR_TRANSACTION_FILE_NAME),
    transactionDict,
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
      tryRemovePackageImportFolder(
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
      tryRemovePackageImportFolder(
        strTransactionFolderPath,
        "Failed to remove a Package staging folder without a transaction",
      );
      continue;
    }

    try {
      const transactionDict = parseTransaction(strTransactionPath);
      const strTargetPath = path.join(
        strExecutorPackageFolderPath,
        transactionDict.targetFolderName,
      );
      const projectRecord = dbSelectProjectDetail(
        transactionDict.projectName,
        transactionDict.projectVersion,
      );

      if (fs.existsSync(strTargetPath) && projectRecord === undefined) {
        loggerMain.warn(
          `Roll back an incomplete Package import: ${transactionDict.projectName}-${transactionDict.projectVersion}`,
        );
        tryRemovePackageImportFolder(
          strTargetPath,
          "Failed to roll back an incomplete Package import",
        );
      } else if (!fs.existsSync(strTargetPath) && projectRecord !== undefined) {
        loggerMain.error(
          "Installed Package folder is missing for database record: " +
            `${transactionDict.projectName}-${transactionDict.projectVersion}`,
        );
      }
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to inspect Package import transaction ${strTransactionFolderPath}: ${String(e)}`,
      );
    } finally {
      tryRemovePackageImportFolder(
        strTransactionFolderPath,
        "Failed to clean a recovered Package import transaction",
      );
    }
  }
}
