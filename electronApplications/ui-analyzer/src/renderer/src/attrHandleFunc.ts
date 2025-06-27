// FileName: attrHandleFunc.ts

export const strSuffixOmit = "-omit";
export const strSuffixRegex = "-regex";

export function removeSuffix(originalText: string, suffix: string): string {
  if (originalText.endsWith(suffix)) {
    return originalText.slice(0, -suffix.length);
  }
  return originalText;
}

export function removePrefix(originalText: string, prefix: string): string {
  if (originalText.startsWith(prefix)) {
    return originalText.slice(prefix.length);
  }
  return originalText;
}

export function modifyKeyName(
  dictToModify: { [key: string]: any },
  originalKeyName: string,
  newKeyName: string
): void {
  // Modify the key's name and keep its order.
  for (const keyName of Object.keys(dictToModify)) {
    if (keyName === originalKeyName) {
      dictToModify[newKeyName] = dictToModify[keyName];
      delete dictToModify[keyName];
    } else {
      // Delete the key so it will after the newKeyName
      const valueCache: any = dictToModify[keyName];
      delete dictToModify[keyName];
      dictToModify[keyName] = valueCache;
    }
  }
}

export const fixTrailingCommas = (jsonText: string): string => {
  // Remove trailing commas before } or ], because the dictionary formatted by Python Black may add them.
  return jsonText.replace(/,(\s*[}\]])/g, "$1");
};
