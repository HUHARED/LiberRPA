// FileName: packageImport.ts

import { dialog } from "electron";
import fs from "fs";

import {
  dbInsertProjectDetail,
  dbSelectProjectDetail,
} from "../Database/projectRepository";
import { getExecutorPackageFolderPath } from "../FileSystem/executorFiles";
import { loggerMain } from "../Logging/logger";
import type { Dict_ProjectPackage_ImportResult } from "../../shared/project";
import { validatePackagedFlowProject } from "./componentManagementClient";
import { extractProjectPackageArchive } from "./packageArchive";
import {
  createProjectPackageImportStaging,
  removePackageImportFolderBestEffort,
  writeProjectPackageImportTransaction,
} from "./packageImportTransaction";
import { readProjectPackageMetadata } from "./packageMetadata";

let boolPackageImportRunning = false;

async function runProjectPackageImport(): Promise<Dict_ProjectPackage_ImportResult> {
  const dialogResult = await dialog.showOpenDialog({
    properties: ["openFile"],
    title: "Select a Flow Project Package",
    filters: [{ name: "LiberRPA Flow Project Package", extensions: ["rpa.zip"] }],
  });
  if (dialogResult.canceled) {
    return { status: "canceled" };
  }
  if (dialogResult.filePaths.length !== 1) {
    throw new Error("Exactly one Flow Project Package must be selected.");
  }

  const strPackageFilePath = dialogResult.filePaths[0];
  const { transactionFolderPath, stagedProjectPath } = createProjectPackageImportStaging();

  let strTargetPath: string | undefined;
  let boolTransactionWritten = false;
  let boolDatabaseCommitted = false;
  try {
    extractProjectPackageArchive(strPackageFilePath, stagedProjectPath);
    const packageMetadata = readProjectPackageMetadata(stagedProjectPath);

    await validatePackagedFlowProject(stagedProjectPath);

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

    writeProjectPackageImportTransaction({
      transactionFolderPath,
      projectName: packageMetadata.name,
      projectVersion: packageMetadata.version,
    });
    boolTransactionWritten = true;

    fs.renameSync(stagedProjectPath, strTargetPath);

    dbInsertProjectDetail(packageMetadata.projectDetail);
    boolDatabaseCommitted = true;

    removePackageImportFolderBestEffort(
      transactionFolderPath,
      "Failed to clean the completed Package import transaction",
    );
    loggerMain.info(
      `Imported Flow Project Package: ${packageMetadata.name}-${packageMetadata.version}`,
    );
    return {
      status: "projectPackageImported",
      name: packageMetadata.name,
      version: packageMetadata.version,
    };
  } catch (e: unknown) {
    let boolRollbackComplete = !boolTransactionWritten;

    if (boolTransactionWritten && !boolDatabaseCommitted) {
      if (strTargetPath === undefined || !fs.existsSync(strTargetPath)) {
        boolRollbackComplete = true;
      } else {
        boolRollbackComplete = removePackageImportFolderBestEffort(
          strTargetPath,
          "Failed to roll back the installed Package folder",
        );
      }
    }

    if (boolRollbackComplete) {
      removePackageImportFolderBestEffort(
        transactionFolderPath,
        "Failed to clean the failed Package import transaction",
      );
    } else {
      loggerMain.error(
        `Keep unresolved Package import transaction: ${transactionFolderPath}`,
      );
    }
    throw e;
  }
}

export async function importProjectPackage(): Promise<Dict_ProjectPackage_ImportResult> {
  if (boolPackageImportRunning) {
    throw new Error("Another Project Package import is already running.");
  }

  boolPackageImportRunning = true;
  try {
    return await runProjectPackageImport();
  } finally {
    boolPackageImportRunning = false;
  }
}
