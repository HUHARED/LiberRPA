// FileName: packageArchiveWorker.ts

import { workerData } from "worker_threads";

import { extractProjectPackageArchive } from "./packageArchive";

export interface PackageArchiveArgs {
  packageFilePath: string;
  stagedProjectPath: string;
}

const archiveArgs = workerData as PackageArchiveArgs;
extractProjectPackageArchive(archiveArgs.packageFilePath, archiveArgs.stagedProjectPath);
