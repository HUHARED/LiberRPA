import type {
  DictPythonEnvironmentSelection,
  DictRunOptions,
} from "../../shared/runOptions";

export interface DictProjectRunDetail
  extends DictRunOptions, DictPythonEnvironmentSelection {
  schedule_name: string | null;
  id: number;
  name: string;
  version: string;
}
