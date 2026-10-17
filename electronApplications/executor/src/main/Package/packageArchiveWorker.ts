// FileName: packageArchiveWorker.ts

import { workerData } from "worker_threads";

import { extractPackageArchive } from "./packageArchive";

export interface PackageArchiveArgs {
  packageFilePath: string;
  stagedPackagePath: string;
}

const archiveArgs = workerData as PackageArchiveArgs;
extractPackageArchive(archiveArgs.packageFilePath, archiveArgs.stagedPackagePath);
