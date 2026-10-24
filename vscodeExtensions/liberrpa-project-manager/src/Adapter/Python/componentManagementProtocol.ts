// FileName: componentManagementProtocol.ts

import type {
  DictComponentManagementWarning,
  DictProtocolDependencyOperation,
} from "../../Domain/ComponentManagement/componentManagementTypes";

export interface DictProtocolRequest_PublishComponent {
  schemaVersion: 1;
  operation: "publishComponent";
  projectPath: string;
}

export interface DictProtocolRequest_ImportComponentWheels {
  schemaVersion: 1;
  operation: "importComponentWheels";
  wheelFilePaths: string[];
}

export interface DictProtocolRequest_RebuildRepositoryIndex {
  schemaVersion: 1;
  operation: "rebuildRepositoryIndex";
}

export interface DictProtocolRequest_GetComponentRepositoryCatalog {
  schemaVersion: 1;
  operation: "getComponentRepositoryCatalog";
}

export interface DictProtocolRequest_GetProjectManifestDefaults {
  schemaVersion: 1;
  operation: "getProjectManifestDefaults";
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
  | DictProtocolRequest_ImportComponentWheels
  | DictProtocolRequest_RebuildRepositoryIndex
  | DictProtocolRequest_GetComponentRepositoryCatalog
  | DictProtocolRequest_GetProjectManifestDefaults
  | DictProtocolRequest_GetProjectDependencyState
  | DictProtocolRequest_BuildProjectDependencyPlan
  | DictProtocolRequest_ApplyProjectDependencyPlan
  | DictProtocolRequest_RepairProjectComponents;

export interface DictProtocolError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface DictProtocolSuccess<T> {
  schemaVersion: 1;
  ok: true;
  result: T;
  warnings: DictComponentManagementWarning[];
}

export interface DictProtocolResponse_Error {
  schemaVersion: 1;
  ok: false;
  error: DictProtocolError;
}

export type DictProtocolSuccess_Raw = DictProtocolSuccess<Record<string, unknown>>;
export type DictProtocolResponse_Raw = DictProtocolSuccess_Raw | DictProtocolResponse_Error;
