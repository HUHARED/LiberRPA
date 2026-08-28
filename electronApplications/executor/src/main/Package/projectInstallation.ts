// FileName: projectInstallation.ts

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
  dbDeleteProject,
  dbSelectProjectBoundSchedules,
  dbSelectProjectDetailById,
} from "../Database/projectRepository";
import { dbHasRunningRunForProject } from "../Database/runHistoryRepository";
import {
  getExecutorPackageFolderPath,
  strExecutorPackageFolderPath,
} from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import { isProjectRunStarting } from "../Run/projectRunner";
import { hasWaitingRunForProject } from "../Scheduler/schedulerEngine";
import { getTargetFolderName } from "./packageArchive";

interface Dict_Transaction_ProjectPackageDelete {
  schemaVersion: 1;
  projectId: number;
  projectName: string;
  projectVersion: string;
  targetFolderName: string;
}

const STR_DELETE_STAGING_FOLDER_NAME = ".delete-staging";
const STR_TRANSACTION_FILE_NAME = "transaction.json";
const STR_STAGED_PROJECT_FOLDER_NAME = "project";

function getDeleteStagingRootPath(): string {
  return path.join(strExecutorPackageFolderPath, STR_DELETE_STAGING_FOLDER_NAME);
}

function parseDeleteTransaction(
  transactionPath: string,
): Dict_Transaction_ProjectPackageDelete {
  const dictTransaction = ensureExactRecord(
    readJsonFile(transactionPath, "Project deletion transaction"),
    ["schemaVersion", "projectId", "projectName", "projectVersion", "targetFolderName"],
    "Project deletion transaction",
  );
  if (dictTransaction.schemaVersion !== 1) {
    throw new Error(`Unsupported Project deletion transaction: ${transactionPath}`);
  }

  const intProjectId = ensurePositiveInteger(
    dictTransaction.projectId,
    "Project deletion transaction.projectId",
  );
  const strProjectName = ensureNonEmptyString(
    dictTransaction.projectName,
    "Project deletion transaction.projectName",
  );
  const strProjectVersion = ensureNonEmptyString(
    dictTransaction.projectVersion,
    "Project deletion transaction.projectVersion",
  );
  const strTargetFolderName = ensureNonEmptyString(
    dictTransaction.targetFolderName,
    "Project deletion transaction.targetFolderName",
  );

  if (getTargetFolderName(strProjectName, strProjectVersion) !== strTargetFolderName) {
    throw new Error(
      `Project deletion transaction target is inconsistent: ${transactionPath}`,
    );
  }

  return {
    schemaVersion: 1,
    projectId: intProjectId,
    projectName: strProjectName,
    projectVersion: strProjectVersion,
    targetFolderName: strTargetFolderName,
  };
}

function removeFolderBestEffort(strFolderPath: string, strContext: string): boolean {
  try {
    fs.rmSync(strFolderPath, { recursive: true, force: true });
    return true;
  } catch (e: unknown) {
    loggerMain.warn(`${strContext}: ${getErrorMessage(e)}`);
    return false;
  }
}

export function deleteInstalledProject(projectId: number): void {
  const dictProject = dbSelectProjectDetailById(projectId);
  if (dictProject === undefined) {
    throw new Error(`Project not found: ${projectId}`);
  }

  const arrBoundSchedule = dbSelectProjectBoundSchedules(projectId);
  if (arrBoundSchedule.length !== 0) {
    throw new Error(
      `Cannot delete Project ${projectId} because it is used by Schedule: ${arrBoundSchedule
        .map((dictSchedule) => dictSchedule.name)
        .join(", ")}.`,
    );
  }
  if (hasWaitingRunForProject(projectId)) {
    throw new Error(`Cannot delete Project ${projectId} while it has a waiting Run.`);
  }
  if (isProjectRunStarting(projectId) || dbHasRunningRunForProject(projectId)) {
    throw new Error(`Cannot delete Project ${projectId} while it is running.`);
  }

  const strTargetPath = getExecutorPackageFolderPath(dictProject.name, dictProject.version);
  if (!fs.existsSync(strTargetPath)) {
    loggerMain.warn(
      `Installed Project folder is already missing: ${dictProject.name}-${dictProject.version}`,
    );
    dbDeleteProject(projectId);
    return;
  }

  const strTransactionFolderPath = path.join(getDeleteStagingRootPath(), randomUUID());
  const strStagedProjectPath = path.join(
    strTransactionFolderPath,
    STR_STAGED_PROJECT_FOLDER_NAME,
  );
  fs.mkdirSync(strTransactionFolderPath, { recursive: true });

  const dictTransaction: Dict_Transaction_ProjectPackageDelete = {
    schemaVersion: 1,
    projectId,
    projectName: dictProject.name,
    projectVersion: dictProject.version,
    targetFolderName: getTargetFolderName(dictProject.name, dictProject.version),
  };
  writeJsonFileAtomic(
    path.join(strTransactionFolderPath, STR_TRANSACTION_FILE_NAME),
    dictTransaction,
  );

  fs.renameSync(strTargetPath, strStagedProjectPath);
  try {
    dbDeleteProject(projectId);
  } catch (e: unknown) {
    let boolRestored = false;
    try {
      if (!fs.existsSync(strTargetPath) && fs.existsSync(strStagedProjectPath)) {
        fs.renameSync(strStagedProjectPath, strTargetPath);
      }
      boolRestored = fs.existsSync(strTargetPath);
    } catch (restoreError: unknown) {
      loggerMain.error(
        `Failed to restore Project folder after database deletion failure: ${getErrorMessage(
          restoreError,
        )}`,
      );
    }

    if (boolRestored) {
      removeFolderBestEffort(
        strTransactionFolderPath,
        "Failed to clean rolled-back Project deletion transaction",
      );
    } else {
      loggerMain.error(
        `Keep Project deletion transaction for recovery: ${strTransactionFolderPath}`,
      );
    }
    throw e;
  }

  removeFolderBestEffort(
    strTransactionFolderPath,
    "Failed to clean completed Project deletion transaction",
  );
  loggerMain.info(`Deleted installed Project: ${dictProject.name}-${dictProject.version}`);
}

export function recoverProjectPackageDeletions(): void {
  const strStagingRootPath = getDeleteStagingRootPath();
  if (!fs.existsSync(strStagingRootPath)) {
    return;
  }

  for (const entryObj of fs.readdirSync(strStagingRootPath, { withFileTypes: true })) {
    const strTransactionFolderPath = path.join(strStagingRootPath, entryObj.name);
    if (!entryObj.isDirectory()) {
      removeFolderBestEffort(
        strTransactionFolderPath,
        "Failed to remove invalid Project deletion staging entry",
      );
      continue;
    }

    const strTransactionPath = path.join(
      strTransactionFolderPath,
      STR_TRANSACTION_FILE_NAME,
    );
    if (!fs.existsSync(strTransactionPath)) {
      removeFolderBestEffort(
        strTransactionFolderPath,
        "Failed to remove Project deletion staging folder without transaction",
      );
      continue;
    }

    let boolRecovered = false;
    try {
      const dictTransaction = parseDeleteTransaction(strTransactionPath);
      const dictProject = dbSelectProjectDetailById(dictTransaction.projectId);
      const strTargetPath = getExecutorPackageFolderPath(
        dictTransaction.projectName,
        dictTransaction.projectVersion,
      );
      const strStagedProjectPath = path.join(
        strTransactionFolderPath,
        STR_STAGED_PROJECT_FOLDER_NAME,
      );

      if (dictProject === undefined) {
        // Database deletion completed. The staged copy belongs to the deleted installation.
        // Do not touch targetPath because the same Project version may have been imported again after the original deletion completed.
        boolRecovered = true;
      } else if (
        dictProject.name !== dictTransaction.projectName ||
        dictProject.version !== dictTransaction.projectVersion
      ) {
        loggerMain.error(
          `Project deletion transaction no longer matches database record ${dictTransaction.projectId}.`,
        );
      } else if (!fs.existsSync(strTargetPath) && fs.existsSync(strStagedProjectPath)) {
        loggerMain.warn(
          `Restore an incomplete Project deletion: ${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
        );
        fs.renameSync(strStagedProjectPath, strTargetPath);
        boolRecovered = true;
      } else if (fs.existsSync(strTargetPath) && fs.existsSync(strStagedProjectPath)) {
        loggerMain.warn(
          "Remove duplicate staged Project from deletion recovery: " +
            `${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
        );
        boolRecovered = removeFolderBestEffort(
          strStagedProjectPath,
          "Failed to remove duplicate staged Project during deletion recovery",
        );
      } else if (fs.existsSync(strTargetPath)) {
        // The delete had not moved the installed folder yet.
        boolRecovered = true;
      } else {
        loggerMain.error(
          "Project folder is missing while recovering deletion: " +
            `${dictTransaction.projectName}-${dictTransaction.projectVersion}`,
        );
      }
    } catch (e: unknown) {
      loggerMain.error(
        `Failed to recover Project deletion transaction ${strTransactionFolderPath}: ${getErrorMessage(e)}`,
      );
    }

    if (boolRecovered) {
      removeFolderBestEffort(
        strTransactionFolderPath,
        "Failed to clean recovered Project deletion transaction",
      );
    } else {
      loggerMain.error(
        `Keep unresolved Project deletion transaction: ${strTransactionFolderPath}`,
      );
    }
  }
}
