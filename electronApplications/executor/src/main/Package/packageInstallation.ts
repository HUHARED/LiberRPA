// FileName: packageInstallation.ts

import { dialog } from "electron";
import fs from "fs";
import path from "path";

import {
  dbInsertProjectDetail,
  dbSelectProjectDetail,
} from "../Database/projectRepository";
import { getExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import type { Dict_ProjectPackage_InstallResult } from "../../shared/project";
import { extractProjectPackageArchive } from "./packageArchive";
import {
  createProjectPackageInstallationStaging,
  removePackageInstallationFolderBestEffort,
  writeProjectPackageInstallationTransaction,
} from "./packageInstallationTransaction";
import { readProjectPackageMetadata } from "./packageMetadata";

let boolPackageInstallationRunning = false;
let strLastPackageFolderPath: string | undefined;

async function runProjectPackageInstallation(
  ensureExecutorRunning: () => void,
): Promise<Dict_ProjectPackage_InstallResult> {
  const dialogResult = await dialog.showOpenDialog({
    defaultPath: strLastPackageFolderPath,
    properties: ["openFile"],
    title: "Select a Flow Project Package",
    filters: [{ name: "LiberRPA Flow Project Package", extensions: ["rpa.zip"] }],
  });
  if (dialogResult.canceled) {
    return { status: "canceled" };
  }

  // Shutdown may have started while the native file dialog was open.
  ensureExecutorRunning();
  if (dialogResult.filePaths.length !== 1) {
    throw new Error("Exactly one Flow Project Package must be selected.");
  }

  const strPackageFilePath = dialogResult.filePaths[0];
  strLastPackageFolderPath = path.dirname(strPackageFilePath);
  const { transactionFolderPath, stagedProjectPath } =
    createProjectPackageInstallationStaging();

  let strTargetPath: string | undefined;
  let boolTransactionWritten = false;
  let boolDatabaseCommitted = false;
  try {
    extractProjectPackageArchive(strPackageFilePath, stagedProjectPath);
    const packageMetadata = readProjectPackageMetadata(stagedProjectPath);

    if (
      dbSelectProjectDetail(packageMetadata.name, packageMetadata.version) !== undefined
    ) {
      throw new Error(
        `Project Package ${packageMetadata.name}-${packageMetadata.version} is already installed.`,
      );
    }

    strTargetPath = getExecutorPackageFolderPath(
      packageMetadata.name,
      packageMetadata.version,
    );
    if (fs.existsSync(strTargetPath)) {
      throw new Error(`The target Package folder already exists: ${strTargetPath}`);
    }

    writeProjectPackageInstallationTransaction({
      transactionFolderPath,
      projectName: packageMetadata.name,
      projectVersion: packageMetadata.version,
    });
    boolTransactionWritten = true;

    fs.renameSync(stagedProjectPath, strTargetPath);

    dbInsertProjectDetail(packageMetadata.projectDetail);
    boolDatabaseCommitted = true;

    removePackageInstallationFolderBestEffort(
      transactionFolderPath,
      "Failed to clean the completed Package installation transaction",
    );
    loggerMain.info(
      `Installed Flow Project Package: ${packageMetadata.name}-${packageMetadata.version}`,
    );
    return {
      status: "projectPackageInstalled",
      name: packageMetadata.name,
      version: packageMetadata.version,
    };
  } catch (e: unknown) {
    let boolRollbackComplete = !boolTransactionWritten;

    if (boolTransactionWritten && !boolDatabaseCommitted) {
      if (strTargetPath === undefined || !fs.existsSync(strTargetPath)) {
        boolRollbackComplete = true;
      } else {
        boolRollbackComplete = removePackageInstallationFolderBestEffort(
          strTargetPath,
          "Failed to roll back the installed Package folder",
        );
      }
    }

    if (boolRollbackComplete) {
      removePackageInstallationFolderBestEffort(
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

export async function installProjectPackage(
  ensureExecutorRunning: () => void,
): Promise<Dict_ProjectPackage_InstallResult> {
  if (boolPackageInstallationRunning) {
    throw new Error("Another Project Package installation is already running.");
  }

  boolPackageInstallationRunning = true;
  try {
    return await runProjectPackageInstallation(ensureExecutorRunning);
  } finally {
    boolPackageInstallationRunning = false;
  }
}
