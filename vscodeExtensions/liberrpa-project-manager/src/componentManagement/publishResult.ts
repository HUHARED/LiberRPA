// FileName: publishResult.ts

import {
  isRecord,
  ensureExactRecord,
  ensureNonEmptyString,
  ensureSha256,
  ensureNonNegativeInteger,
} from "../typeCheck";
import type {
  DictProtocolResult_PublishBase,
  DictProtocolResult_Publish,
} from "./protocol";

const SET_PUBLISH_RESULT_BASE_KEYS = new Set([
  "status",
  "componentId",
  "packageName",
  "astSnippetsFile",
  "snippetsJsoncFile",
  "generatedCount",
  "skippedCount",
  "warningCount",
]);
const SET_PUBLISH_RESULT_PUBLISHED_KEYS = new Set([
  ...SET_PUBLISH_RESULT_BASE_KEYS,
  "version",
  "wheelFile",
  "sha256",
  "excludedCount",
  "handWrittenCount",
  "finalCount",
]);

function parsePublishBase(
  value: Record<string, unknown>,
  sourceName: string,
): DictProtocolResult_PublishBase {
  return {
    componentId: ensureNonEmptyString(value["componentId"], `${sourceName}.componentId`),
    packageName: ensureNonEmptyString(value["packageName"], `${sourceName}.packageName`),
    astSnippetsFile: ensureNonEmptyString(
      value["astSnippetsFile"],
      `${sourceName}.astSnippetsFile`,
    ),
    snippetsJsoncFile: ensureNonEmptyString(
      value["snippetsJsoncFile"],
      `${sourceName}.snippetsJsoncFile`,
    ),
    generatedCount: ensureNonNegativeInteger(
      value["generatedCount"],
      `${sourceName}.generatedCount`,
    ),
    skippedCount: ensureNonNegativeInteger(
      value["skippedCount"],
      `${sourceName}.skippedCount`,
    ),
    warningCount: ensureNonNegativeInteger(
      value["warningCount"],
      `${sourceName}.warningCount`,
    ),
  };
}

export function parsePublishComponentResult(value: unknown): DictProtocolResult_Publish {
  if (!isRecord(value)) {
    throw new Error("Publish Component result must be an object.");
  }

  const status = value["status"];
  if (status === "preparationCreated") {
    const dictValue = ensureExactRecord(
      value,
      SET_PUBLISH_RESULT_BASE_KEYS,
      "Publish Component result",
    );
    return {
      ...parsePublishBase(dictValue, "Publish Component result"),
      status,
    };
  }

  if (status === "published" || status === "alreadyPublished") {
    const dictValue = ensureExactRecord(
      value,
      SET_PUBLISH_RESULT_PUBLISHED_KEYS,
      "Publish Component result",
    );
    return {
      ...parsePublishBase(dictValue, "Publish Component result"),
      status,
      version: ensureNonEmptyString(
        dictValue["version"],
        "Publish Component result.version",
      ),
      wheelFile: ensureNonEmptyString(
        dictValue["wheelFile"],
        "Publish Component result.wheelFile",
      ),
      sha256: ensureSha256(dictValue["sha256"], "Publish Component result.sha256"),
      excludedCount: ensureNonNegativeInteger(
        dictValue["excludedCount"],
        "Publish Component result.excludedCount",
      ),
      handWrittenCount: ensureNonNegativeInteger(
        dictValue["handWrittenCount"],
        "Publish Component result.handWrittenCount",
      ),
      finalCount: ensureNonNegativeInteger(
        dictValue["finalCount"],
        "Publish Component result.finalCount",
      ),
    };
  }

  throw new Error(`Unsupported Publish Component result status: ${String(status)}.`);
}
