// FileName: protocol.ts

import type { DictProjectManifestV1 } from "../projectManifest";

// align protocol types with Python.
export type Str_ProjectType = "flow" | "component";

export interface DictComponentManagementWarning {
  code: string;
  message: string;
  details?: Record<string, unknown>;

  file?: string;
  line?: number;
  functionName?: string;
  snippetKey?: string;

  [key: string]: unknown;
}

export interface DictProtocolDependencyOperation_Add {
  operation: "addComponentDependency";
  componentId: string;
  requirement: string;
}

export interface DictProtocolDependencyOperation_Update {
  operation: "updateComponents";
  componentIds: string[];
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
  | DictProtocolDependencyOperation_ChangeRequirement
  | DictProtocolDependencyOperation_Remove;

export interface DictProtocolRequest_PublishComponent {
  schemaVersion: 1;
  operation: "publishComponent";
  projectPath: string;
}

export interface DictProtocolRequest_RebuildRepositoryIndex {
  schemaVersion: 1;
  operation: "rebuildRepositoryIndex";
}

export interface DictProtocolRequest_ImportComponentWheels {
  schemaVersion: 1;
  operation: "importComponentWheels";
  wheelPaths: string[];
}

export interface DictProtocolRequest_GetComponentRepositoryCatalog {
  schemaVersion: 1;
  operation: "getComponentRepositoryCatalog";
}

export interface DictProtocolRequest_GetProjectDependencyState {
  schemaVersion: 1;
  operation: "getProjectDependencyState";
  projectPath: string;
}

export interface DictProtocolRequest_BuildProjectDependencyPlan {
  schemaVersion: 1;
  operation: "buildProjectDependencyPlan";
  projectPath: string;
  dependencyOperation: DictProtocolDependencyOperation;
}

export interface DictProtocolRequest_ApplyProjectDependencyPlan {
  schemaVersion: 1;
  operation: "applyProjectDependencyPlan";
  projectPath: string;
  dependencyOperation: DictProtocolDependencyOperation;
  confirmedPlanSha256: string;
}

export interface DictProtocolRequest_RepairProjectComponents {
  schemaVersion: 1;
  operation: "repairProjectComponents";
  projectPath: string;
}

export type DictProtocolRequest =
  | DictProtocolRequest_PublishComponent
  | DictProtocolRequest_RebuildRepositoryIndex
  | DictProtocolRequest_ImportComponentWheels
  | DictProtocolRequest_GetComponentRepositoryCatalog
  | DictProtocolRequest_GetProjectDependencyState
  | DictProtocolRequest_BuildProjectDependencyPlan
  | DictProtocolRequest_ApplyProjectDependencyPlan
  | DictProtocolRequest_RepairProjectComponents;

export interface DictProtocolResult_PublishBase {
  componentId: string;
  packageName: string;
  astSnippetsFile: string;
  snippetsJsoncFile: string;
  generatedCount: number;
  skippedCount: number;
  warningCount: number;
}

export interface DictProtocolResult_Publish_PreparationCreated extends DictProtocolResult_PublishBase {
  status: "preparationCreated";
}

export interface DictProtocolResult_Publish_Published extends DictProtocolResult_PublishBase {
  status: "published" | "alreadyPublished";
  version: string;
  wheelFile: string;
  sha256: string;
  excludedCount: number;
  handWrittenCount: number;
  finalCount: number;
}

export type DictProtocolResult_Publish =
  | DictProtocolResult_Publish_PreparationCreated
  | DictProtocolResult_Publish_Published;

export interface DictProtocolResult_RepositoryIndexRebuilt {
  status: "repositoryIndexRebuilt";
  componentCount: number;
  versionCount: number;
}

export interface DictProtocolResult_ComponentWheelsImported_Component {
  sourcePath: string;
  componentId: string;
  packageName: string;
  version: string;
  wheelFile: string;
  sha256: string;
  status: "imported" | "alreadyImported";
}

export interface DictProtocolResult_ComponentWheelsImported {
  status: "componentWheelsImported";
  importedCount: number;
  alreadyImportedCount: number;
  components: DictProtocolResult_ComponentWheelsImported_Component[];
}

export interface DictRepository_ComponentVersion {
  version: string;
  displayName: string;
  description: string;
  manifestSchemaVersion: 1;
  wheelFile: string;
  sha256: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

export interface DictProtocolResult_RepositoryCatalog_Component {
  componentId: string;
  packageName: string;
  versions: DictRepository_ComponentVersion[];
}

export interface DictProtocolResult_RepositoryCatalog {
  status: "componentRepositoryCatalog";
  repositoryPath: string;
  componentCount: number;
  versionCount: number;
  components: DictProtocolResult_RepositoryCatalog_Component[];
}

export interface DictComponentsLock_Root_FlowProject {
  manifestFile: "flow.json";
  manifestSchemaVersion: 1;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
  resolutionInputSha256: string;
}

export interface DictComponentsLock_Root_ComponentProject {
  manifestFile: "component.json";
  manifestSchemaVersion: 1;
  componentId: string;
  packageName: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
  resolutionInputSha256: string;
}

export type DictComponentsLock_Root =
  | DictComponentsLock_Root_FlowProject
  | DictComponentsLock_Root_ComponentProject;

export interface DictComponentsLock_Component {
  manifestSchemaVersion: 1;
  packageName: string;
  displayName: string;
  version: string;
  wheelFile: string;
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
  componentsPath: string;
  componentCount: number;
  fileCount: number;
}

export interface DictProtocolResult_ProjectDependencyState {
  status: "projectDependencyState";
  projectPath: string;
  projectType: Str_ProjectType;
  manifest: DictProjectManifestV1;
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
  sourceManifest: DictProjectManifestV1;
  sourceComponentsLock: DictComponentsLock_File | null;
  targetManifest: DictProjectManifestV1;
  targetComponentsLock: DictComponentsLock_File | null;
  directDependencyChanges: DictProjectDependency_DirectChange[];
  resolvedComponentChanges: DictProjectDependency_ResolvedChange[];
}

export interface DictProtocolResult_ProjectDependencyPlanApplied {
  status: "projectDependencyPlanApplied";
  planSha256: string;
  targetManifest: DictProjectManifestV1;
  targetComponentsLock: DictComponentsLock_File | null;
  directDependencyChanges: DictProjectDependency_DirectChange[];
  resolvedComponentChanges: DictProjectDependency_ResolvedChange[];
  componentsFolder: DictProtocolResult_ComponentsFolder | null;
}

export interface DictProtocolResult_ProjectComponentsRepaired {
  status: "projectComponentsRepaired";
  componentsFolder: DictProtocolResult_ComponentsFolder;
}

export interface DictProtocolError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface DictProtocolSuccess_Raw {
  schemaVersion: 1;
  ok: true;
  result: Record<string, unknown>;
  warnings: DictComponentManagementWarning[];
}

export interface DictProtocolResponse_Error {
  schemaVersion: 1;
  ok: false;
  error: DictProtocolError;
}

export type DictProtocolResponse_Raw = DictProtocolSuccess_Raw | DictProtocolResponse_Error;
