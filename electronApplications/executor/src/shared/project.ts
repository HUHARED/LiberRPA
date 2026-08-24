// FileName: project.ts

import type {
  DictColumns_RunOptions_ExecutionEnvironment,
  DictColumns_RunOptions_NeedConvert_DB,
  DictColumns_RunOptions_NeedConvert_TS,
  DictColumns_RunOptions_TimeoutAndLog,
  TypeColumns_RunOptions_NeedConvert,
} from "./runOptions";

interface DictColumns_Base_DB {
  id: number;
  created_at_ms: number;
  updated_at_ms: number;
}

type TypeColumns_ModifyTime = "created_at_ms" | "updated_at_ms";

export interface DictColumns_Project_Detail_DB
  extends
    DictColumns_Base_DB,
    DictColumns_RunOptions_NeedConvert_DB,
    DictColumns_RunOptions_TimeoutAndLog,
    DictColumns_RunOptions_ExecutionEnvironment {
  name: string;
  version: string;
  description: string;
  version_summary: string;
}

export type DictColumns_Project_Detail = Omit<
  DictColumns_Project_Detail_DB,
  TypeColumns_RunOptions_NeedConvert
> &
  DictColumns_RunOptions_NeedConvert_TS;

export type DictColumns_Project_Detail_ToInsert = Omit<
  DictColumns_Project_Detail_DB,
  "id" | TypeColumns_ModifyTime
>;

export type DictProjectPackageImportResult =
  | { status: "canceled" }
  | {
      status: "projectPackageImported";
      name: string;
      version: string;
      packageFilePath: string;
      installedFolderPath: string;
    };

export type DictColumns_Project_Detail_ToUpdate = Omit<
  DictColumns_Project_Detail_DB,
  TypeColumns_ModifyTime
>;
