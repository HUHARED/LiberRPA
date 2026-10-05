// FileName: packagePreparation.ts

import { execFile } from "child_process";
import { createHash, randomUUID } from "crypto";
import fs from "fs";
import path from "path";
import { promisify } from "util";

import { ensureNonEmptyString, ensureRecord } from "../Common/validation";
import {
  buildPythonProcessEnvironment,
  getPythonEnvironmentPath,
  strDocumentsFolderPath,
} from "../Config/environment";
import { extractProjectPackageArchive } from "../Package/packageArchive";
import { readProjectPackageMetadata } from "../Package/packageMetadata";
import { requestConsole } from "./consoleApi";
import type { ConsoleCredentialSnapshot } from "./consoleContextBridge";
import type { ConsoleAssignment } from "./workRepository";

const execFileAsync = promisify(execFile);
const abortPreparation = new AbortController();

export function stopPackagePreparation(): void {
  abortPreparation.abort();
}

const INT_MAX_PACKAGE_BYTES = 512 * 1024 ** 2;

export async function verifyPythonPackageEnvironment(
  packagePath: string,
  environmentName: string,
): Promise<void> {
  const strEnvironmentPath = getPythonEnvironmentPath(environmentName);
  await execFileAsync(
    path.join(strEnvironmentPath, "python.exe"),
    [
      "-c",
      "import importlib.metadata,json,sys; from packaging.specifiers import SpecifierSet; m=json.load(open(sys.argv[1],encoding='utf-8-sig')); v=importlib.metadata.version('liberrpa'); assert v in SpecifierSet(m['requiresLiberrpa']), 'Installed liberrpa '+v+' does not satisfy '+m['requiresLiberrpa']",
      path.join(packagePath, "flow.json"),
    ],
    {
      env: buildPythonProcessEnvironment({
        pythonEnvironmentPath: strEnvironmentPath,
        pythonPathEntries: [],
      }),
      timeout: 15_000,
      maxBuffer: 64 * 1024,
      windowsHide: true,
    },
  );
}

async function preparePackageFiles(
  assignment: ConsoleAssignment,
  credential: ConsoleCredentialSnapshot,
): Promise<string> {
  const strSha256 = ensureNonEmptyString(assignment.snapshot.sha256, "Package SHA256");
  if (!/^[a-f0-9]{64}$/.test(strSha256) || !/^[a-f0-9-]{36}$/i.test(assignment.package_id))
    throw new Error("Console package identity is invalid.");
  const strOriginHash = createHash("sha256").update(credential.consoleUrl).digest("hex");
  const strCacheRoot = path.join(
    strDocumentsFolderPath,
    "LiberRPA/ConsolePackage",
    strOriginHash,
    assignment.package_id,
  );
  const strPackagePath = path.join(strCacheRoot, strSha256);
  if (!fs.existsSync(strPackagePath)) {
    fs.mkdirSync(strCacheRoot, { recursive: true });
    const strStaging = path.join(strCacheRoot, `.staging-${randomUUID()}`);
    const strArchive = `${strStaging}.zip`;
    try {
      const response = await requestConsole(
        credential.consoleUrl,
        `executor/packages/${assignment.package_id}/downloads/`,
        credential.token,
        {},
      );
      const strTransferId = ensureNonEmptyString(
        response.transfer_id,
        "Package download transfer",
      );
      const metadata = ensureRecord(response.package, "Download package");
      if (metadata.sha256 !== strSha256)
        throw new Error("Package digest changed during preparation.");
      const download = await fetch(
        `${credential.consoleUrl}/api/clients/executor/packages/downloads/${encodeURIComponent(strTransferId)}/content/`,
        {
          headers: { Authorization: `Bearer ${credential.token}` },
          redirect: "error",
          credentials: "omit",
          signal: AbortSignal.any([AbortSignal.timeout(120_000), abortPreparation.signal]),
        },
      );
      if (!download.ok || !download.body)
        throw new Error(`Package download failed (${download.status}).`);
      const digest = createHash("sha256");
      const intFile = fs.openSync(strArchive, "wx");
      let intBytes = 0;
      try {
        for await (const chunk of download.body) {
          intBytes += chunk.byteLength;
          if (intBytes > INT_MAX_PACKAGE_BYTES)
            throw new Error("Package download exceeds 512 MiB.");
          digest.update(chunk);
          fs.writeSync(intFile, chunk);
        }
      } finally {
        fs.closeSync(intFile);
      }
      if (intBytes !== metadata.size_bytes || digest.digest("hex") !== strSha256)
        throw new Error("Downloaded package size or SHA256 does not match Console.");
      extractProjectPackageArchive(strArchive, strStaging);
      const packageMetadata = await readProjectPackageMetadata(strStaging);
      if (
        packageMetadata.name !== assignment.snapshot.project_name ||
        packageMetadata.version !== assignment.snapshot.project_version
      )
        throw new Error("Package identity does not match the accepted Job.");
      fs.renameSync(strStaging, strPackagePath);
    } finally {
      fs.rmSync(strArchive, { force: true });
      fs.rmSync(strStaging, { force: true, recursive: true });
    }
  }
  await verifyPythonPackageEnvironment(
    strPackagePath,
    ensureNonEmptyString(assignment.snapshot.python_environment_name, "Python environment"),
  );
  return strPackagePath;
}

const mapPackagePreparation = new Map<string, Promise<string>>();

export async function prepareConsolePackage(
  assignment: ConsoleAssignment,
  credential: ConsoleCredentialSnapshot,
): Promise<string> {
  const strKey = JSON.stringify([
    credential.consoleUrl,
    assignment.package_id,
    assignment.snapshot.sha256,
    assignment.snapshot.python_environment_name,
  ]);
  const existing = mapPackagePreparation.get(strKey);
  if (existing) return await existing;
  const promisePreparation = preparePackageFiles(assignment, credential);
  mapPackagePreparation.set(strKey, promisePreparation);
  try {
    return await promisePreparation;
  } finally {
    if (mapPackagePreparation.get(strKey) === promisePreparation)
      mapPackagePreparation.delete(strKey);
  }
}
