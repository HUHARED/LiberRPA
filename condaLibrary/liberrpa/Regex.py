# FileName: Regex.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import re


def _handle_flags(
    ignoreCase: bool = False,
    multiLine: bool = False,
    dotAll: bool = False,
    verbose: bool = False,
    ascii: bool = False,
    local: bool = False,
) -> int:
    flags = 0
    if ignoreCase:
        flags |= re.IGNORECASE
    if multiLine:
        flags |= re.MULTILINE
    if dotAll:
        flags |= re.DOTALL
    if verbose:
        flags |= re.VERBOSE
    if ascii:
        flags |= re.ASCII
    if local:
        flags |= re.LOCALE

    return flags


@Log.trace()
def find_one(
    strObj: str,
    pattern: str,
    ignoreCase: bool = False,
    multiLine: bool = False,
    dotAll: bool = False,
    verbose: bool = False,
    ascii: bool = False,
    local: bool = False,
) -> str | None:
    """
    Finds the first occurrence of a pattern in the given string.

    Parameters:
        strObj: The string to search.
        pattern: The regex pattern to match.
        ignoreCase: If True, match case-insensitively.
        multiLine: If True, treat input as multiple lines.
        dotAll: If True, '.' matches any character, including newline.
        verbose: If True, allows for more readable regex patterns.
        ascii: If True, restricts matching to ASCII characters.
        local: If True, uses locale-dependent matching.

    Returns:
        str | None: The matched string or None if no match is found.
    """
    flags = _handle_flags(
        ignoreCase=ignoreCase, multiLine=multiLine, dotAll=dotAll, verbose=verbose, ascii=ascii, local=local
    )
    match = re.search(pattern, strObj, flags)
    return match.group() if match else None


@Log.trace()
def find_all(
    strObj: str,
    pattern: str,
    ignoreCase: bool = False,
    multiLine: bool = False,
    dotAll: bool = False,
    verbose: bool = False,
    ascii: bool = False,
    local: bool = False,
) -> list[str]:
    """
    Finds all occurrences of a pattern in the given string.

    Parameters:
        strObj: The string to search.
        pattern: The regex pattern to match.
        ignoreCase: If True, match case-insensitively.
        multiLine: If True, treat input as multiple lines.
        dotAll: If True, '.' matches any character, including newline.
        verbose: If True, allows for more readable regex patterns.
        ascii: If True, restricts matching to ASCII characters.
        local: If True, uses locale-dependent matching.

    Returns:
        list[str]: A list of all matched strings.
    """
    flags = _handle_flags(
        ignoreCase=ignoreCase, multiLine=multiLine, dotAll=dotAll, verbose=verbose, ascii=ascii, local=local
    )
    return re.findall(pattern, strObj, flags)


@Log.trace()
def match_start(
    strObj: str,
    pattern: str,
    ignoreCase: bool = False,
    multiLine: bool = False,
    dotAll: bool = False,
    verbose: bool = False,
    ascii: bool = False,
    local: bool = False,
) -> str | None:
    """
    Checks for a match only at the start of the string.

    Parameters:
        strObj: The string to check.
        pattern: The regex pattern to match.
        ignoreCase: If True, match case-insensitively.
        multiLine: If True, treat input as multiple lines.
        dotAll: If True, '.' matches any character, including newline.
        verbose: If True, allows for more readable regex patterns.
        ascii: If True, restricts matching to ASCII characters.
        local: If True, uses locale-dependent matching.

    Returns:
        str | None: The matched string or None if no match is found.
    """
    flags = _handle_flags(
        ignoreCase=ignoreCase, multiLine=multiLine, dotAll=dotAll, verbose=verbose, ascii=ascii, local=local
    )
    match = re.match(pattern, strObj, flags)
    return match.group() if match else None


@Log.trace()
def match_full(
    strObj: str,
    pattern: str,
    ignoreCase: bool = False,
    multiLine: bool = False,
    dotAll: bool = False,
    verbose: bool = False,
    ascii: bool = False,
    local: bool = False,
) -> str | None:
    """
    Checks for a match that covers the entire string.

    Parameters:
        strObj: The string to check.
        pattern: The regex pattern to match.
        ignoreCase: If True, match case-insensitively.
        multiLine: If True, treat input as multiple lines.
        dotAll: If True, '.' matches any character, including newline.
        verbose: If True, allows for more readable regex patterns.
        ascii: If True, restricts matching to ASCII characters.
        local: If True, uses locale-dependent matching.

    Returns:
        str | None: The matched string or None if no match is found.
    """
    flags = _handle_flags(
        ignoreCase=ignoreCase, multiLine=multiLine, dotAll=dotAll, verbose=verbose, ascii=ascii, local=local
    )
    match = re.fullmatch(pattern, strObj, flags)
    return match.group() if match else None


@Log.trace()
def split(
    strObj: str,
    pattern: str,
    maxSplit: int = 0,
    ignoreCase: bool = False,
    multiLine: bool = False,
    dotAll: bool = False,
    verbose: bool = False,
    ascii: bool = False,
    local: bool = False,
) -> list[str]:
    """
    Splits the string at each occurrence of the pattern.

    Parameters:
        strObj: The string to split.
        pattern: The regex pattern to use for splitting.
        maxSplit: The maximum number of splits to perform; 0 means no limit.
        ignoreCase: If True, match case-insensitively.
        multiLine: If True, treat input as multiple lines.
        dotAll: If True, '.' matches any character, including newline.
        verbose: If True, allows for more readable regex patterns.
        ascii: If True, restricts matching to ASCII characters.
        local: If True, uses locale-dependent matching.

    Returns:
        list[str]: A list of substrings after splitting.
    """
    flags = _handle_flags(
        ignoreCase=ignoreCase, multiLine=multiLine, dotAll=dotAll, verbose=verbose, ascii=ascii, local=local
    )
    if maxSplit <= 0:
        # Split all.
        maxSplit = 0
    return re.split(pattern, strObj, maxSplit, flags)


@Log.trace()
def replace(
    strObj: str,
    pattern: str,
    newStr: str,
    count: int = 0,
    ignoreCase: bool = False,
    multiLine: bool = False,
    dotAll: bool = False,
    verbose: bool = False,
    ascii: bool = False,
    local: bool = False,
) -> str:
    """
    Replaces occurrences of the pattern in the string with a new string.

    Parameters:
        strObj: The original string.
        pattern: The regex pattern to match.
        newStr: The string to replace matches with.
        count: The maximum number of replacements to perform; 0 means all.
        ignoreCase: If True, match case-insensitively.
        multiLine: If True, treat input as multiple lines.
        dotAll: If True, '.' matches any character, including newline.
        verbose: If True, allows for more readable regex patterns.
        ascii: If True, restricts matching to ASCII characters.
        local: If True, uses locale-dependent matching.

    Returns:
        str: The modified string with replacements made.
    """
    flags = _handle_flags(
        ignoreCase=ignoreCase, multiLine=multiLine, dotAll=dotAll, verbose=verbose, ascii=ascii, local=local
    )
    if count <= 0:
        # Replace all.
        count = 0
    return re.sub(pattern, newStr, strObj, count, flags)


if __name__ == "__main__":
    print(find_all("first line\nsecond line", "a", multiLine=True, dotAll=True))
    # print(
    #     match_full(
    #         "first line\nsecond line",
    #         "first line\nsecond lin",
    #     )
    # )
    # print(split("123123", "1", maxSplit=0))
    # print(replace("123123", "1", "4", count=0))
    
