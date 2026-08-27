// FileName: componentManagementProtocol.ts

import { ensureExactRecord, ensureRecord, ensureString } from "../Common/validation";

export interface Dict_Request_ValidatePackagedFlowProject {
  schemaVersion: 1;
  operation: "validatePackagedFlowProject";
  projectPath: string;
}

export function createValidatePackagedFlowProjectRequest(
  projectPath: string,
): Dict_Request_ValidatePackagedFlowProject {
  return {
    schemaVersion: 1,
    operation: "validatePackagedFlowProject",
    projectPath: projectPath,
  };
}

function parseProtocolJson(output: string): Record<string, unknown> {
  let value: unknown;
  try {
    value = JSON.parse(output);
  } catch (e: unknown) {
    throw new Error("Component Management returned invalid JSON on stdout.", {
      cause: e,
    });
  }
  return ensureRecord(value, "Component Management response");
}

export function validatePackagedFlowProjectResponse(output: string): void {
  const dictResponse = parseProtocolJson(output);
  if (dictResponse.schemaVersion !== 1 || typeof dictResponse.ok !== "boolean") {
    throw new Error("Component Management returned an invalid protocol response.");
  }

  if (dictResponse.ok) {
    const dictSuccess = ensureExactRecord(
      dictResponse,
      ["schemaVersion", "ok", "result", "warnings"],
      "Component Management success response",
    );
    const dictResult = ensureExactRecord(
      dictSuccess.result,
      ["status"],
      "Component Management success result",
    );
    if (dictResult.status !== "packagedFlowProjectValidated") {
      throw new Error("Component Management returned an unexpected success status.");
    }
    if (!Array.isArray(dictSuccess.warnings)) {
      throw new Error("Component Management success response.warnings must be an array.");
    }
    return;
  }

  const dictFailure = ensureExactRecord(
    dictResponse,
    ["schemaVersion", "ok", "error"],
    "Component Management error response",
  );
  const dictError = ensureExactRecord(
    dictFailure.error,
    ["code", "message", "details"],
    "Component Management error",
  );
  const strCode = ensureString(dictError.code, "Component Management error.code");
  const strMessage = ensureString(dictError.message, "Component Management error.message");
  const dictDetails = ensureRecord(dictError.details, "Component Management error.details");
  const strDetails = JSON.stringify(dictDetails, null, 2);
  throw new Error(
    `[${strCode}] ${strMessage}` + (strDetails === "{}" ? "" : `\n${strDetails}`),
  );
}
