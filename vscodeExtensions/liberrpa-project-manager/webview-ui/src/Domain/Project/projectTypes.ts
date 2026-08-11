// FileName: projectTypes.ts
// IMPORTANT: Keep the Extension and Webview copies of this file synchronized.
// Synchronization is verified by scripts/checkSynchronizedFiles.mjs.
// - src/Domain/Project/projectTypes.ts
// - webview-ui/src/Domain/Project/projectTypes.ts

export type Str_ProjectType = "flow" | "component";

export interface DictProjectManifest_Flow {
  schemaVersion: 1;
  name: string;

  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

export interface DictProjectManifest_Component {
  schemaVersion: 1;
  id: string;
  packageName: string;
  displayName: string;

  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

export type DictProjectManifest = DictProjectManifest_Flow | DictProjectManifest_Component;

export interface DictCreateProjectInput {
  templateName: string;
  projectType: Str_ProjectType;

  targetFolderPath: string;
  projectFolderName: string;

  packageName: string;
  displayName: string;
  version: string;
  description: string;
}

export interface DictProjectTemplateInfo {
  templateName: string;
  projectType: Str_ProjectType;

  defaultVersion: string;
  defaultDescription: string;
}

export interface DictPackageProjectInput {
  outputFolderPath: string;
  includeVscodeSettings: boolean;
  includeGitRepository: boolean;
}

export interface DictProjectPackageResult {
  packageFilePath: string;
  packageFileName: string;
  fileCount: number;
  folderCount: number;
  uncompressedSizeBytes: number;
  packageSizeBytes: number;
}
