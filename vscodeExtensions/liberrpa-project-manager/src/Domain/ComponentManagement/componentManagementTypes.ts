// FileName: componentManagementTypes.ts
// IMPORTANT: Keep the Extension and Webview copies of this file synchronized.
// Synchronization is verified by scripts/checkSynchronizedFiles.mjs.
// - src/Domain/ComponentManagement/componentManagementTypes.ts
// - webview-ui/src/Domain/ComponentManagement/componentManagementTypes.ts

import type { Str_ProjectType, DictProjectManifest } from "../Project/projectTypes";

export interface DictComponentManagementWarning_Operation {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface DictComponentManagementWarning_SnippetDiagnostic {
  code: string;
  message: string;
  file: string;
  line: number;
  functionName?: string;
}

export interface DictComponentManagementWarning_SnippetConfig {
  code: string;
  message: string;
  snippetKey: string;
}

export type DictComponentManagementWarning =
  | DictComponentManagementWarning_SnippetDiagnostic
  | DictComponentManagementWarning_SnippetConfig
  | DictComponentManagementWarning_Operation;

export interface DictProtocolDependencyOperation_Add {
  operation: "addComponentDependency";
  componentId: string;
  requirement: string;
}

export interface DictProtocolDependencyOperation_Update {
  operation: "updateComponents";
  componentIds: string[];
}

export interface DictProtocolDependencyOperation_Resolve {
  operation: "resolveProjectDependencies";
}

export interface DictProtocolDependencyOperation_ChangeRequirement {
  operation: "changeComponentRequirement";
  componentId: string;
  requirement: string;
}

export interface DictProtocolDependencyOperation_Remove {
  operation: "removeComponentDependency";
  componentId: string;
}

export type DictProtocolDependencyOperation =
  | DictProtocolDependencyOperation_Add
  | DictProtocolDependencyOperation_Update
  | DictProtocolDependencyOperation_Resolve
  | DictProtocolDependencyOperation_ChangeRequirement
  | DictProtocolDependencyOperation_Remove;

export interface _DictProtocolResult_PublishBase {
  componentId: string;
  packageName: string;

  astSnippetsFile: string;
  snippetsJsoncFile: string;
  generatedCount: number;
  skippedCount: number;
  warningCount: number;
}

export interface _DictProtocolResult_Publish_PreparationCreated extends _DictProtocolResult_PublishBase {
  status: "preparationCreated";
}

export interface _DictProtocolResult_Publish_Published extends _DictProtocolResult_PublishBase {
  status: "published" | "alreadyPublished";
  version: string;

  excludedCount: number;
  handWrittenCount: number;
  finalCount: number;

  wheelFileName: string;
  sha256: string;
}

export type DictProtocolResult_Publish =
  | _DictProtocolResult_Publish_PreparationCreated
  | _DictProtocolResult_Publish_Published;

export interface DictProtocolResult_ComponentWheelsImported_Component {
  sourceWheelFilePath: string;

  componentId: string;
  packageName: string;
  version: string;

  wheelFileName: string;
  sha256: string;

  status: "imported" | "alreadyImported";
}

export interface DictProtocolResult_ComponentWheelsImported {
  status: "componentWheelsImported";
  importedCount: number;
  alreadyImportedCount: number;
  components: DictProtocolResult_ComponentWheelsImported_Component[];
}

export interface DictProtocolResult_RepositoryIndexRebuilt {
  status: "repositoryIndexRebuilt";
  componentCount: number;
  versionCount: number;
}

export interface DictRepository_ComponentVersionEntry {
  version: string;
  displayName: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;

  wheelFileName: string;
  sha256: string;
}

export interface DictProtocolResult_RepositoryCatalog_Component {
  componentId: string;
  packageName: string;
  versions: DictRepository_ComponentVersionEntry[];
}

export interface DictProtocolResult_RepositoryCatalog {
  status: "componentRepositoryCatalog";
  repositoryPath: string;
  componentCount: number;
  versionCount: number;
  components: DictProtocolResult_RepositoryCatalog_Component[];
}

export interface DictComponentsLock_Root_FlowProject {
  manifestFileName: "flow.json";

  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

export interface DictComponentsLock_Root_ComponentProject {
  manifestFileName: "component.json";

  componentId: string;
  packageName: string;

  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

export type DictComponentsLock_Root =
  | DictComponentsLock_Root_FlowProject
  | DictComponentsLock_Root_ComponentProject;

export interface DictComponentsLock_Component {
  packageName: string;
  displayName: string;
  version: string;
  wheelFileName: string;
  sha256: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

export interface DictComponentsLock_File {
  schemaVersion: 1;
  root: DictComponentsLock_Root;
  components: Record<string, DictComponentsLock_Component>;
}

export type Str_ProjectDependency_LockState =
  | "notRequired"
  | "missing"
  | "invalid"
  | "stale"
  | "valid";

export type Str_ProjectDependency_ComponentsState =
  | "notRequired"
  | "unverified"
  | "missing"
  | "damaged"
  | "valid";

export type Str_ProjectDependency_EnvironmentState =
  | "unknown"
  | "compatible"
  | "incompatible";

export type Str_ProjectDependency_RepairState =
  | "notApplicable"
  | "available"
  | "repositoryUnavailable"
  | "wheelMissing"
  | "wheelHashMismatch";

export interface DictProjectDependency_DirectChange {
  componentId: string;
  change: "added" | "removed" | "requirementChanged";
  previousRequirement?: string;
  targetRequirement?: string;
}

export interface DictProjectDependency_ResolvedChange {
  componentId: string;
  packageName: string;
  displayName: string;
  change: "added" | "removed" | "upgraded" | "downgraded";
  previousVersion?: string;
  targetVersion?: string;
}

export interface DictProtocolResult_ComponentsFolder {
  componentsFolderPath: string;
  componentCount: number;
  fileCount: number;
}

export interface DictProtocolResult_ProjectDependencyState {
  status: "projectDependencyState";
  projectPath: string;
  projectType: Str_ProjectType;
  manifest: DictProjectManifest;
  componentsLock: DictComponentsLock_File | null;
  lockState: Str_ProjectDependency_LockState;
  componentsState: Str_ProjectDependency_ComponentsState;
  environmentState: Str_ProjectDependency_EnvironmentState;
  repairState: Str_ProjectDependency_RepairState;
  details: Record<string, unknown>;
}

export interface DictProtocolResult_ProjectDependencyPlan {
  status: "projectDependencyPlanCreated";
  planSha256: string;
  sourceManifest: DictProjectManifest;
  sourceComponentsLock: DictComponentsLock_File | null;
  targetManifest: DictProjectManifest;
  targetComponentsLock: DictComponentsLock_File | null;
  directDependencyChanges: DictProjectDependency_DirectChange[];
  resolvedComponentChanges: DictProjectDependency_ResolvedChange[];
}

export interface DictProtocolResult_ProjectDependencyPlanApplied {
  status: "projectDependencyPlanApplied";
  planSha256: string;
  targetManifest: DictProjectManifest;
  targetComponentsLock: DictComponentsLock_File | null;
  directDependencyChanges: DictProjectDependency_DirectChange[];
  resolvedComponentChanges: DictProjectDependency_ResolvedChange[];
  componentsFolder: DictProtocolResult_ComponentsFolder | null;
}

export interface DictProtocolResult_ProjectComponentsRepaired {
  status: "projectComponentsRepaired";
  componentsFolder: DictProtocolResult_ComponentsFolder;
}
