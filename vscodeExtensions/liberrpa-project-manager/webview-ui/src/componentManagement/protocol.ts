// FileName: protocol.ts

export type Str_ProjectType = "flow" | "component";

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

export interface DictFlowManifestV1 {
  schemaVersion: 1;
  name: string;
  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

export interface DictComponentManifestV1 {
  schemaVersion: 1;
  id: string;
  packageName: string;
  displayName: string;
  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

export type DictProjectManifestV1 = DictFlowManifestV1 | DictComponentManifestV1;

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
