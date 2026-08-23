import { randomUUID } from "crypto";
import fs from "fs";
import path from "path";

import { isRecord } from "../Common/validation";
import { dbSelectProjectDetail } from "../Database/projectRepository";
import { strExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import { getTargetFolderName } from "./packageArchive";

interface DictPackageImportTransaction {
  schemaVersion: 1;
  state: "prepared";
  projectName: string;
  projectVersion: string;
  targetFolderName: string;
}

interface DictPackageImportStagingPaths {
  transactionFolderPath: string;
  stagedProjectPath: string;
}

const STR_STAGING_FOLDER_NAME = ".staging";
const STR_TRANSACTION_FILE_NAME = "transaction.json";
const STR_STAGED_PROJECT_FOLDER_NAME = "project";

function readJsonFile(strFilePath: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(strFilePath, { encoding: "utf-8" }));
  } catch (e: unknown) {
    throw new Error(`Failed to read JSON file: ${strFilePath}`, { cause: e });
  }
}

function writeJsonFileAtomic(strFilePath: string, value: unknown): void {
  const strTempPath = `${strFilePath}.tmp`;
  fs.rmSync(strTempPath, { force: true });
  fs.writeFileSync(strTempPath, `${JSON.stringify(value, null, 2)}\n`, {
    encoding: "utf-8",
  });
  fs.renameSync(strTempPath, strFilePath);
}

function hasExactKeys(
  value: Record<string, unknown>,
  setExpectedKey: Set<string>,
): boolean {
  const arrKey = Object.keys(value);
  return (
    arrKey.length === setExpectedKey.size &&
    arrKey.every((strKey) => setExpectedKey.has(strKey))
  );
}

function parseTransaction(strTransactionPath: string): DictPackageImportTransaction {
  const value = readJsonFile(strTransactionPath);
  const setKey = new Set([
    "schemaVersion",
    "state",
    "projectName",
    "projectVersion",
    "targetFolderName",
  ]);
  if (
    !isRecord(value) ||
    !hasExactKeys(value, setKey) ||
    value.schemaVersion !== 1 ||
    value.state !== "prepared" ||
    typeof value.projectName !== "string" ||
    typeof value.projectVersion !== "string" ||
    typeof value.targetFolderName !== "string"
  ) {
    throw new Error(`Invalid Package import transaction: ${strTransactionPath}`);
  }
  if (
    getTargetFolderName(value.projectName, value.projectVersion) !== value.targetFolderName
  ) {
    throw new Error(
      `Package import transaction target is inconsistent: ${strTransactionPath}`,
    );
  }
  return {
    schemaVersion: 1,
    state: value.state,
    projectName: value.projectName,
    projectVersion: value.projectVersion,
    targetFolderName: value.targetFolderName,
  };
}

function removeFolder(strFolderPath: string): void {
  fs.rmSync(strFolderPath, { recursive: true, force: true });
}

export function tryRemovePackageImportFolder(
  strFolderPath: string,
  strContext: string,
): void {
  try {
    removeFolder(strFolderPath);
  } catch (e: unknown) {
    loggerMain.warn(`${strContext}: ${e instanceof Error ? e.message : String(e)}`);
  }
}

export function createProjectPackageImportStaging(): DictPackageImportStagingPaths {
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

  const transaction: DictPackageImportTransaction = {
    schemaVersion: 1,
    state: "prepared",
    projectName,
    projectVersion,
    targetFolderName,
  };
  writeJsonFileAtomic(
    path.join(transactionFolderPath, STR_TRANSACTION_FILE_NAME),
    transaction,
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
      const transaction = parseTransaction(strTransactionPath);
      const strTargetPath = path.join(
        strExecutorPackageFolderPath,
        transaction.targetFolderName,
      );
      const projectRecord = dbSelectProjectDetail(
        transaction.projectName,
        transaction.projectVersion,
      );

      if (fs.existsSync(strTargetPath) && projectRecord === undefined) {
        loggerMain.warn(
          `Roll back an incomplete Package import: ${transaction.projectName}-${transaction.projectVersion}`,
        );
        tryRemovePackageImportFolder(
          strTargetPath,
          "Failed to roll back an incomplete Package import",
        );
      } else if (!fs.existsSync(strTargetPath) && projectRecord !== undefined) {
        loggerMain.error(
          "Installed Package folder is missing for database record: " +
            `${transaction.projectName}-${transaction.projectVersion}`,
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
