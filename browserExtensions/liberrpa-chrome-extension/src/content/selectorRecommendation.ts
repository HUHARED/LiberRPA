// FileName: selectorRecommendation.ts

import type { DictFinalAttr, DictLayerHtml } from "./interface";
import {
  addIndexForTheLayer,
  getDocumentElementsMatchingAttributes,
} from "./elementAttrFunc";

const INT_MAX_IDENTITY_VALUE_LENGTH = 120;
const INT_MAX_DIRECT_TEXT_LENGTH = 80;
const INT_MAX_CLASS_NAME_LENGTH = 120;
const INT_MAX_CLASS_TOKEN_COUNT = 3;
const INT_MAX_RECOMMENDED_IDENTITY_ATTRIBUTE_COUNT = 3;

const ARR_RECOMMENDED_IDENTITY_ATTRIBUTE_NAME = [
  "id",
  "name",
  "aria-label",
  "aria-labelledby",
  "alt",
  "directText",
  "tableColumnName",
  "className",
] as const;

const SET_VOLATILE_CLASS_TOKEN = new Set([
  "active",
  "checked",
  "disabled",
  "expanded",
  "focus",
  "focused",
  "hidden",
  "hover",
  "open",
  "selected",
  "show",
]);

const REGEX_UUID = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/iu;
const REGEX_LONG_DIGIT_SEQUENCE = /\d{8,}/u;
const REGEX_LONG_HEX_TOKEN = /(?:^|[-_:])[0-9a-f]{12,}(?:$|[-_:])/iu;

type RecommendedIdentityAttributeName =
  (typeof ARR_RECOMMENDED_IDENTITY_ATTRIBUTE_NAME)[number];

type RecommendedIdentityAttribute = readonly [RecommendedIdentityAttributeName, string];

export function getRecommendedHtmlTargetSpecification(
  elementTarget: HTMLElement,
  dictAllTargetAttributes: DictFinalAttr,
  boolUsePath: boolean,
): DictLayerHtml {
  try {
    if (boolUsePath) {
      if (typeof dictAllTargetAttributes.path !== "string") {
        throw new Error("The generated HTML target attributes do not contain a path.");
      }

      return {
        tagName: dictAllTargetAttributes.tagName,
        path: dictAllTargetAttributes.path,
      };
    }

    return getRecommendedIndexSpecification(elementTarget, dictAllTargetAttributes);
  } catch (e) {
    console.warn(
      "Failed to generate a concise HTML selector recommendation; use the complete target attributes.",
      e,
    );
    return getCompleteTargetSpecification(dictAllTargetAttributes);
  }
}

function getRecommendedIndexSpecification(
  elementTarget: HTMLElement,
  dictAllTargetAttributes: DictFinalAttr,
): DictLayerHtml {
  const dictRecommended: DictLayerHtml = {
    tagName: dictAllTargetAttributes.tagName,
  };

  const strType = dictAllTargetAttributes.type;
  if (isReadableSingleLineValue(strType, 40)) {
    dictRecommended.type = strType;
  }

  const arrIdentityAttribute = getRecommendedIdentityAttributes(dictAllTargetAttributes);
  const boolOriginalUsesIndex =
    dictAllTargetAttributes.childIndex !== undefined ||
    dictAllTargetAttributes.documentIndex !== undefined;

  if (boolOriginalUsesIndex) {
    // Keep every suitable identity attribute from an already index-based selector.
    // This branch removes clearly unsuitable attributes without trying to minimize an ambiguous target.
    addIdentityAttributes(
      dictRecommended,
      arrIdentityAttribute,
      arrIdentityAttribute.length,
    );
    return addIndexForTheLayer(elementTarget, dictRecommended);
  }

  const intAddedIdentityAttributeCount = addIdentityAttributes(
    dictRecommended,
    arrIdentityAttribute,
    1,
  );
  if (isUniqueTarget(elementTarget, dictRecommended)) {
    return dictRecommended;
  }

  const intAdditionalIdentityAttributeCount = addIdentityAttributes(
    dictRecommended,
    arrIdentityAttribute.slice(intAddedIdentityAttributeCount),
    INT_MAX_RECOMMENDED_IDENTITY_ATTRIBUTE_COUNT - intAddedIdentityAttributeCount,
  );
  if (
    intAdditionalIdentityAttributeCount > 0 &&
    isUniqueTarget(elementTarget, dictRecommended)
  ) {
    return dictRecommended;
  }

  return addIndexForTheLayer(elementTarget, dictRecommended);
}

function getRecommendedIdentityAttributes(
  dictAllTargetAttributes: DictFinalAttr,
): RecommendedIdentityAttribute[] {
  const arrIdentityAttribute: RecommendedIdentityAttribute[] = [];

  for (const strAttributeName of ARR_RECOMMENDED_IDENTITY_ATTRIBUTE_NAME) {
    const strValue = dictAllTargetAttributes[strAttributeName];
    if (!isRecommendedIdentityAttribute(strAttributeName, strValue)) {
      continue;
    }

    arrIdentityAttribute.push([strAttributeName, strValue]);
  }

  return arrIdentityAttribute;
}

function isRecommendedIdentityAttribute(
  strAttributeName: RecommendedIdentityAttributeName,
  value: string | undefined,
): value is string {
  if (strAttributeName === "directText" || strAttributeName === "tableColumnName") {
    return isReadableSingleLineValue(value, INT_MAX_DIRECT_TEXT_LENGTH);
  }

  if (strAttributeName === "className") {
    return isRecommendedClassName(value);
  }

  return (
    isReadableSingleLineValue(value, INT_MAX_IDENTITY_VALUE_LENGTH) &&
    !looksGeneratedValue(value)
  );
}

function isReadableSingleLineValue(
  value: string | undefined,
  intMaxLength: number,
): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= intMaxLength &&
    value.trim() === value &&
    !/[\r\n]/u.test(value)
  );
}

function isRecommendedClassName(value: string | undefined): value is string {
  if (!isReadableSingleLineValue(value, INT_MAX_CLASS_NAME_LENGTH)) {
    return false;
  }

  const arrClassToken = value.split(/\s+/u).filter(Boolean);
  return (
    arrClassToken.length > 0 &&
    arrClassToken.length <= INT_MAX_CLASS_TOKEN_COUNT &&
    arrClassToken.every(
      (strClassToken) =>
        !isVolatileClassToken(strClassToken) && !looksGeneratedValue(strClassToken),
    )
  );
}

function isVolatileClassToken(strClassToken: string): boolean {
  return strClassToken
    .toLowerCase()
    .split(/[-_:]+/u)
    .some((strTokenPart) => SET_VOLATILE_CLASS_TOKEN.has(strTokenPart));
}

function looksGeneratedValue(strValue: string): boolean {
  return (
    REGEX_UUID.test(strValue) ||
    REGEX_LONG_DIGIT_SEQUENCE.test(strValue) ||
    REGEX_LONG_HEX_TOKEN.test(strValue)
  );
}

function addIdentityAttributes(
  dictRecommended: DictLayerHtml,
  arrIdentityAttribute: RecommendedIdentityAttribute[],
  intMaxCount: number,
): number {
  let intAddedCount = 0;

  for (const [strAttributeName, strValue] of arrIdentityAttribute) {
    if (intAddedCount >= intMaxCount) {
      break;
    }

    dictRecommended[strAttributeName] = strValue;
    intAddedCount += 1;
  }

  return intAddedCount;
}

function isUniqueTarget(
  elementTarget: HTMLElement,
  dictRecommended: DictLayerHtml,
): boolean {
  const arrMatchedElement = getDocumentElementsMatchingAttributes(dictRecommended);
  return arrMatchedElement.length === 1 && arrMatchedElement[0] === elementTarget;
}

function getCompleteTargetSpecification(
  dictAllTargetAttributes: DictFinalAttr,
): DictLayerHtml {
  const dictComplete: DictLayerHtml = {};

  for (const [strKey, strValue] of Object.entries(dictAllTargetAttributes)) {
    if (!strKey.startsWith("secondary-") && typeof strValue === "string") {
      dictComplete[strKey] = strValue;
    }
  }

  return dictComplete;
}
