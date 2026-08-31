// FileName: snippetCompletionMatching.ts

/**
 * Match prefixes of consecutive words without skipping characters inside a word.
 *
 * Every completed word fragment consumes at least two characters. The final
 * fragment may contain one character so typing `ex` -> `exo` -> `exop` keeps
 * `Excel.open_excel_file` relevant throughout the same suggestion session.
 */
function matchesConsecutiveWordPrefixes(
  searchText: string,
  arrWord: readonly string[],
): boolean {
  const setFailedState = new Set<string>();

  const matchesFrom = (wordIndex: number, searchIndex: number): boolean => {
    if (wordIndex >= arrWord.length) {
      return false;
    }

    const strState = `${wordIndex}:${searchIndex}`;
    if (setFailedState.has(strState)) {
      return false;
    }

    const strWord = arrWord[wordIndex];
    const intRemainingLength = searchText.length - searchIndex;
    let intSharedLength = 0;
    while (
      intSharedLength < strWord.length &&
      intSharedLength < intRemainingLength &&
      strWord[intSharedLength] === searchText[searchIndex + intSharedLength]
    ) {
      intSharedLength += 1;
    }

    if (intSharedLength === intRemainingLength) {
      return true;
    }

    for (let intLength = 2; intLength <= intSharedLength; intLength += 1) {
      if (matchesFrom(wordIndex + 1, searchIndex + intLength)) {
        return true;
      }
    }

    setFailedState.add(strState);
    return false;
  };

  for (let intWordIndex = 0; intWordIndex < arrWord.length; intWordIndex += 1) {
    if (matchesFrom(intWordIndex, 0)) {
      return true;
    }
  }

  return false;
}

/**
 * Apply a conservative relevance gate before VS Code performs its own filtering.
 *
 * Supported forms are a full prefix, a suffix starting at a dot/underscore/space
 * boundary, and prefixes of consecutive words, such as `exop` or `opExFi`.
 * Matching is case-insensitive, including an explicitly typed LiberRPA qualifier.
 * An empty search is allowed only after a matching known qualifier.
 */
export function matchesSnippetCompletion(
  searchText: string,
  snippetPrefix: string,
  qualifier?: string,
): boolean {
  let strCandidate = snippetPrefix;

  if (qualifier !== undefined) {
    const intDotIndex = snippetPrefix.lastIndexOf(".");
    if (
      intDotIndex === -1 ||
      snippetPrefix.slice(0, intDotIndex).toLowerCase() !== qualifier.toLowerCase()
    ) {
      return false;
    }

    strCandidate = snippetPrefix.slice(intDotIndex + 1);
  }

  if (searchText.length === 0) {
    return qualifier !== undefined && strCandidate.length > 0;
  }

  const strSearchLower = searchText.toLowerCase();
  const strCandidateLower = strCandidate.toLowerCase();
  if (strCandidateLower.startsWith(strSearchLower)) {
    return true;
  }

  const arrWord: string[] = [];

  for (const wordMatch of strCandidateLower.matchAll(/[^._\s]+/g)) {
    // Preserve separators for searches such as `to_upper` and `get_last`.
    if (strCandidateLower.slice(wordMatch.index).startsWith(strSearchLower)) {
      return true;
    }
    arrWord.push(wordMatch[0]);
  }

  return matchesConsecutiveWordPrefixes(strSearchLower, arrWord);
}
