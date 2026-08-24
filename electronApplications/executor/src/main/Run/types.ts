import type { TypeProjectSource } from "../../shared/project";
import type {
  DictPythonEnvironmentSelection,
  DictRunOptions,
} from "../../shared/runOptions";

export interface DictProjectRunDetail
  extends DictRunOptions, DictPythonEnvironmentSelection {
  schedule_name: string | null;
  project_source: TypeProjectSource;
  id: number;
  name: string;
  version: string;
}
