// FileName: jsonFile.ts

import fs from "fs";
import path from "path";

export function readJsonFile(filePath: string, sourceName: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(filePath, { encoding: "utf-8" }));
  } catch (e: unknown) {
    throw new Error(`Failed to read ${sourceName}: ${filePath}`, { cause: e });
  }
}

export function writeJsonFileAtomic(filePath: string, value: unknown): void {
  const strTempFilePath = path.join(
    path.dirname(filePath),
    `.${path.basename(filePath)}.${process.pid}.tmp`,
  );

  fs.rmSync(strTempFilePath, { force: true });
  try {
    fs.writeFileSync(strTempFilePath, `${JSON.stringify(value, null, 2)}\n`, {
      encoding: "utf-8",
    });
    fs.renameSync(strTempFilePath, filePath);
  } catch (e: unknown) {
    fs.rmSync(strTempFilePath, { force: true });
    throw e;
  }
}
