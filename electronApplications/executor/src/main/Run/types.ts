// FileName: types.ts

import type {
  Dict_PythonEnvironmentSelection,
  Dict_RunOptions,
} from "../../shared/runOptions";

export interface Dict_ProjectRun_Detail
  extends Dict_RunOptions, Dict_PythonEnvironmentSelection {
  schedule_name: string | null;
  id: number;
  name: string;
  version: string;
}
