// FileName: managedImportRecognition.ts

import type {
  DictImportsInfo,
  DictImportSourceConfig,
} from "../../Domain/Snippet/snippetTypes";

interface ManagedImportSymbol {
  importSource: string;
  importName: string;
}

export interface ManagedImportSymbolIndex {
  arrKnownName: string[];
  mapSymbol: ReadonlyMap<string, ManagedImportSymbol>;
}

function getUsageName(
  strImportSource: string,
  strImportName: string,
  sourceConfig: DictImportSourceConfig,
): string {
  return sourceConfig.aliasMode === "source_module"
    ? `${strImportSource}_${strImportName}`
    : strImportName;
}

export function buildManagedImportSymbolIndex(
  importSourceDict: Record<string, DictImportSourceConfig>,
): ManagedImportSymbolIndex {
  const mapSymbol = new Map<string, ManagedImportSymbol>();
  const setAmbiguousName = new Set<string>();

  for (const [strImportSource, sourceConfig] of Object.entries(importSourceDict)) {
    for (const strImportName of sourceConfig.order) {
      const strUsageName = getUsageName(strImportSource, strImportName, sourceConfig);
      const existingSymbol = mapSymbol.get(strUsageName);

      if (
        existingSymbol !== undefined &&
        (existingSymbol.importSource !== strImportSource ||
          existingSymbol.importName !== strImportName)
      ) {
        mapSymbol.delete(strUsageName);
        setAmbiguousName.add(strUsageName);
        continue;
      }

      if (!setAmbiguousName.has(strUsageName)) {
        mapSymbol.set(strUsageName, {
          importSource: strImportSource,
          importName: strImportName,
        });
      }
    }
  }

  return {
    arrKnownName: [...mapSymbol.keys()].sort(),
    mapSymbol,
  };
}

export function buildManagedImportsFromReferencedNames(
  arrReferencedName: readonly string[],
  symbolIndex: ManagedImportSymbolIndex,
): DictImportsInfo {
  const dictImport: DictImportsInfo = {};

  for (const strReferencedName of arrReferencedName) {
    const symbol = symbolIndex.mapSymbol.get(strReferencedName);
    if (symbol === undefined) {
      continue;
    }

    dictImport[symbol.importSource] ??= [];
    dictImport[symbol.importSource].push(symbol.importName);
  }

  return dictImport;
}
