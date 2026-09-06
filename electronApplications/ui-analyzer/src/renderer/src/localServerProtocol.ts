// FileName: localServerProtocol.ts

import type {
  DictEleTreeItem,
  DictForUiAnalyzer,
  ElementTreeResult,
  Selector,
  UiAnalyzerServerMessage,
} from "../../shared/interface";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringRecord(value: unknown): value is Record<string, string> {
  if (!isRecord(value)) {
    return false;
  }

  return Object.values(value).every((itemValue) => typeof itemValue === "string");
}

function isNonEmptyStringRecord(value: unknown): value is Record<string, string> {
  return isStringRecord(value) && Object.keys(value).length > 0;
}

function isNonEmptyStringRecordArray(value: unknown): value is Record<string, string>[] {
  return (
    Array.isArray(value) &&
    value.every((itemValue: unknown) => isNonEmptyStringRecord(itemValue))
  );
}

function isNonNegativeSafeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0;
}

function isNonNegativeSafeIntegerText(value: string): boolean {
  if (!/^(?:0|[1-9]\d*)$/u.test(value)) {
    return false;
  }

  return Number.isSafeInteger(Number(value));
}

function isPositiveSafeIntegerText(value: string): boolean {
  return /^(?:[1-9]\d*)$/u.test(value) && Number.isSafeInteger(Number(value));
}

function isSelector(value: unknown): value is Selector {
  if (!isRecord(value) || !isStringRecord(value.window)) {
    return false;
  }

  if (!("category" in value)) {
    return !("specification" in value);
  }

  if (value.category !== "uia" && value.category !== "html" && value.category !== "image") {
    return false;
  }

  return (
    Array.isArray(value.specification) &&
    value.specification.length > 0 &&
    value.specification.every(isStringRecord)
  );
}

function isRecommendedWindow(
  value: unknown,
  dictAllWindowAttributes: Record<string, string>,
): value is Record<string, string> {
  if (
    !isNonEmptyStringRecord(value) ||
    value.ControlTypeName !== dictAllWindowAttributes.ControlTypeName
  ) {
    return false;
  }

  return Object.entries(value).every(([strKey, strValue]) => {
    if (strKey === "Index") {
      return isNonNegativeSafeIntegerText(strValue);
    }

    return dictAllWindowAttributes[strKey] === strValue;
  });
}

function isRecommendedHtmlSpecification(
  value: unknown,
  arrAllSpecification: Record<string, string>[],
): value is Record<string, string>[] {
  if (!isNonEmptyStringRecordArray(value) || value.length !== 1) {
    return false;
  }

  const dictAllTargetAttributes = arrAllSpecification[arrAllSpecification.length - 1];
  const dictRecommendedAttributes = value[0];
  if (dictAllTargetAttributes === undefined || dictRecommendedAttributes === undefined) {
    return false;
  }

  if (dictRecommendedAttributes.tagName !== dictAllTargetAttributes.tagName) {
    return false;
  }

  const setCalculatedAttribute = new Set(["childIndex", "documentIndex"]);
  return Object.entries(dictRecommendedAttributes).every(([strKey, strValue]) => {
    if (setCalculatedAttribute.has(strKey)) {
      return isNonNegativeSafeIntegerText(strValue);
    }

    return dictAllTargetAttributes[strKey] === strValue;
  });
}

function isRecommendedUiaSpecification(
  value: unknown,
  arrAllSpecification: Record<string, string>[],
): value is Record<string, string>[] {
  if (!isNonEmptyStringRecordArray(value) || value.length !== arrAllSpecification.length) {
    return false;
  }

  return value.every((dictRecommendedAttributes, intLayerIndex) => {
    const dictAllLayerAttributes = arrAllSpecification[intLayerIndex];
    if (
      dictAllLayerAttributes === undefined ||
      dictRecommendedAttributes.ControlTypeName !== dictAllLayerAttributes.ControlTypeName
    ) {
      return false;
    }

    const strAllDepth = dictAllLayerAttributes.Depth;
    if (
      (strAllDepth === undefined && "Depth" in dictRecommendedAttributes) ||
      (strAllDepth !== undefined &&
        (dictRecommendedAttributes.Depth !== strAllDepth ||
          !isPositiveSafeIntegerText(strAllDepth)))
    ) {
      return false;
    }

    return Object.entries(dictRecommendedAttributes).every(([strKey, strValue]) => {
      if (strKey === "Index") {
        return isNonNegativeSafeIntegerText(strValue);
      }

      return dictAllLayerAttributes[strKey] === strValue;
    });
  });
}

export function isDictForUiAnalyzer(value: unknown): value is DictForUiAnalyzer {
  if (
    !isRecord(value) ||
    !isSelector(value.selector) ||
    !isStringRecord(value.attributes)
  ) {
    return false;
  }

  if (value.preview !== undefined && typeof value.preview !== "string") {
    return false;
  }

  if (
    value.recommendedWindow !== undefined &&
    !isRecommendedWindow(value.recommendedWindow, value.selector.window)
  ) {
    return false;
  }

  if (value.recommendedSpecification === undefined) {
    return true;
  }

  if (!("category" in value.selector)) {
    return false;
  }

  if (value.selector.category === "html") {
    return isRecommendedHtmlSpecification(
      value.recommendedSpecification,
      value.selector.specification,
    );
  }

  if (value.selector.category === "uia") {
    return isRecommendedUiaSpecification(
      value.recommendedSpecification,
      value.selector.specification,
    );
  }

  return false;
}

function collectElementTreeIds(
  value: unknown,
  setElementId: Set<number>,
): value is DictEleTreeItem {
  if (
    !isRecord(value) ||
    !isNonNegativeSafeInteger(value.id) ||
    setElementId.has(value.id) ||
    typeof value.title !== "string" ||
    !isStringRecord(value.attributes)
  ) {
    return false;
  }

  setElementId.add(value.id);

  return (
    value.children === undefined ||
    (Array.isArray(value.children) &&
      value.children.every((childValue) => collectElementTreeIds(childValue, setElementId)))
  );
}

export function isElementTreeResult(value: unknown): value is ElementTreeResult {
  if (!Array.isArray(value) || value.length !== 3) {
    return false;
  }

  const [arrTree, arrOpenedId, intActivatedId] = value;
  if (!Array.isArray(arrTree) || arrTree.length === 0) {
    return false;
  }

  const setElementId = new Set<number>();
  if (!arrTree.every((itemValue) => collectElementTreeIds(itemValue, setElementId))) {
    return false;
  }

  if (
    !Array.isArray(arrOpenedId) ||
    !arrOpenedId.every(
      (itemValue) => isNonNegativeSafeInteger(itemValue) && setElementId.has(itemValue),
    )
  ) {
    return false;
  }

  return (
    new Set(arrOpenedId).size === arrOpenedId.length &&
    isNonNegativeSafeInteger(intActivatedId) &&
    setElementId.has(intActivatedId)
  );
}

export function isValidateResult(value: unknown): value is { validate: boolean } {
  return isRecord(value) && typeof value.validate === "boolean";
}

export function parseUiAnalyzerServerMessage(data: unknown): UiAnalyzerServerMessage {
  if (typeof data !== "string") {
    throw new Error("Local Server response must be a JSON string.");
  }

  let parsedData: unknown;
  try {
    parsedData = JSON.parse(data);
  } catch {
    throw new Error("Failed to parse Local Server response JSON.");
  }

  if (
    !isRecord(parsedData) ||
    !Number.isSafeInteger(parsedData.operationId) ||
    (parsedData.operationId as number) <= 0
  ) {
    throw new Error("Local Server response has no valid operationId.");
  }

  if (parsedData.messageType === "operationCompleted") {
    return {
      operationId: parsedData.operationId as number,
      messageType: "operationCompleted",
    };
  }

  if (
    parsedData.messageType !== "operationResult" &&
    parsedData.messageType !== "elementTreeResult"
  ) {
    throw new Error("Local Server response has an unknown messageType.");
  }

  if (typeof parsedData.boolSuccess !== "boolean" || !("data" in parsedData)) {
    throw new Error("Local Server response has an invalid result envelope.");
  }

  if (parsedData.boolSuccess === false && typeof parsedData.data !== "string") {
    throw new Error("Local Server error response has no valid message.");
  }

  return {
    operationId: parsedData.operationId as number,
    messageType: parsedData.messageType,
    boolSuccess: parsedData.boolSuccess,
    data: parsedData.data,
  };
}
