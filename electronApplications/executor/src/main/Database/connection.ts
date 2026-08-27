// FileName: connection.ts

import Database from "better-sqlite3";
import fs from "fs";
import path from "path";

import { strDocumentsFolderPath } from "../Config/environment";
import { loggerMain } from "../Logging/logger";

const INT_DATABASE_SCHEMA_VERSION = 1;
const STR_DATABASE_FOLDER_PATH = path.join(strDocumentsFolderPath, "LiberRPA/AppData");
const STR_DATABASE_FILE_PATH = path.join(STR_DATABASE_FOLDER_PATH, "ExecutorData.db");
const STR_INIT_DATABASE_SCRIPT_PATH = path.join(
  __dirname,
  "../../resources/InitDatabase.sql",
);

let databaseObj: Database.Database | undefined;

export function initializeDatabase(): void {
  loggerMain.debug("--initializeDatabase--");
  fs.mkdirSync(STR_DATABASE_FOLDER_PATH, { recursive: true });

  if (!fs.existsSync(STR_DATABASE_FILE_PATH)) {
    databaseObj = createDatabase();
    return;
  }

  const existingDatabaseObj = openDatabase(STR_DATABASE_FILE_PATH);
  const intSchemaVersion = getDatabaseSchemaVersionOrClose(existingDatabaseObj);

  if (intSchemaVersion === INT_DATABASE_SCHEMA_VERSION) {
    databaseObj = existingDatabaseObj;
    loggerMain.info(`Opened Executor database schema ${intSchemaVersion}.`);
    return;
  }

  existingDatabaseObj.close();
  const strBackupPath = backupDatabaseFiles();
  loggerMain.warn(
    `Backed up Executor database schema ${intSchemaVersion} to ${strBackupPath}.`,
  );
  databaseObj = createDatabase();
}

export function closeDatabase(): void {
  if (databaseObj === undefined) {
    return;
  }

  databaseObj.close();
  databaseObj = undefined;
}

function openDatabase(databasePath: string): Database.Database {
  const openedDatabaseObj = new Database(databasePath, {
    verbose: (message?: unknown) => {
      loggerMain.debug(`[SQLite] ${String(message)}`);
    },
  });
  openedDatabaseObj.pragma("foreign_keys = ON");
  return openedDatabaseObj;
}

function createDatabase(): Database.Database {
  loggerMain.info("Create Executor database.");
  const newDatabaseObj = openDatabase(STR_DATABASE_FILE_PATH);

  try {
    const strInitScript = fs.readFileSync(STR_INIT_DATABASE_SCRIPT_PATH, {
      encoding: "utf-8",
    });
    newDatabaseObj.exec(strInitScript);

    const intSchemaVersion = getDatabaseSchemaVersion(newDatabaseObj);
    if (intSchemaVersion !== INT_DATABASE_SCHEMA_VERSION) {
      throw new Error(
        `The initialized database schema is ${intSchemaVersion}, expected ${INT_DATABASE_SCHEMA_VERSION}.`,
      );
    }

    return newDatabaseObj;
  } catch (e: unknown) {
    newDatabaseObj.close();
    removeDatabaseFiles(STR_DATABASE_FILE_PATH);
    throw e;
  }
}

function getDatabaseSchemaVersionOrClose(targetDatabaseObj: Database.Database): number {
  try {
    return getDatabaseSchemaVersion(targetDatabaseObj);
  } catch (e: unknown) {
    targetDatabaseObj.close();
    throw e;
  }
}

function getDatabaseSchemaVersion(targetDatabaseObj: Database.Database): number {
  const value = targetDatabaseObj.pragma("user_version", { simple: true });
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new Error(`Invalid Executor database schema version: ${String(value)}`);
  }
  return value;
}

function backupDatabaseFiles(): string {
  const strTimestamp = new Date().toISOString().replace(/[-:.]/g, "");
  const strBackupPath = path.join(
    STR_DATABASE_FOLDER_PATH,
    `ExecutorData.backup.${strTimestamp}.db`,
  );

  for (const strSuffix of ["", "-wal", "-shm", "-journal"]) {
    const strSourcePath = STR_DATABASE_FILE_PATH + strSuffix;
    if (fs.existsSync(strSourcePath)) {
      fs.renameSync(strSourcePath, strBackupPath + strSuffix);
    }
  }

  return strBackupPath;
}

function removeDatabaseFiles(databasePath: string): void {
  for (const strSuffix of ["", "-wal", "-shm", "-journal"]) {
    fs.rmSync(databasePath + strSuffix, { force: true });
  }
}

export function getDatabase(): Database.Database {
  if (databaseObj === undefined) {
    throw new Error("Executor database has not been initialized.");
  }
  return databaseObj;
}
