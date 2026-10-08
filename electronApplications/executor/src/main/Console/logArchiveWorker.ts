// FileName: logArchiveWorker.ts

import fs from "fs";
import path from "path";
import { workerData } from "worker_threads";
import AdmZip from "adm-zip";

export interface LogArchiveArgs {
  logFolderPath: string;
  archiveFilePath: string;
}

const archiveArgs = workerData as LogArchiveArgs;
const arrName = fs
  .readdirSync(archiveArgs.logFolderPath)
  .filter((strName) => /^human_read_.+\.log(?:\.\d+)?$/.test(strName));
if (!arrName.length)
  throw new Error("The original HumanReadableLog files are unavailable.");

const zipObj = new AdmZip();
for (const strName of arrName)
  zipObj.addLocalFile(path.join(archiveArgs.logFolderPath, strName));
zipObj.writeZip(archiveArgs.archiveFilePath);
