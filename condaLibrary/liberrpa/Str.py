# FileName: Str.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from typing import Literal


@Log.trace()
def replace(strObj: str, old: str, new: str, count: int = -1) -> str:
    """
    Replaces occurrences of a substring with a new substring in the given string.

    Parameters:
        strObj: The original string.
        old: The substring to be replaced.
        new: The substring to replace with.
        count: Maximum number of occurrences to replace. Default is -1 (all occurrences).

    Returns:
        str: The modified string.
    """
    return strObj.replace(old, new, count)


@Log.trace()
def split(strObj: str, separator: str, maxSplit: int = -1) -> list[str]:
    """
    Splits the string into a list based on the given separator.

    Parameters:
        strObj: The string to be split.
        separator: The delimiter used to split the string.
        maxSplit: Maximum number of splits. Default is -1 (all occurrences).

    Returns:
        list[str]: A list of split strings.
    """
    if maxSplit <= 0:
        maxSplit = -1
    return strObj.split(separator, maxSplit)


@Log.trace()
def split_lines(strObj: str, keepends: bool = False) -> list[str]:
    """
    Splits the string into lines.

    Parameters:
        strObj: The string to split into lines.
        keepends: If True, line breaks are included in the resulting list.

    Returns:
        list[str]: A list of lines from the string.
    """
    return strObj.splitlines(keepends)


@Log.trace()
def fill(strObj: str, width: int, character: str = "0") -> str:
    """
    Pads the string with a specified character to the desired width.

    Parameters:
        strObj: The original string.
        width: The desired total width of the string after padding.
        character: The character to use for padding. Default is '0'.

    Returns:
        str: The padded string.
    """
    if len(character) != 1:
        raise ValueError(f"The argument character'{character}' should be a one-length string.")
    if len(strObj) >= width:
        return strObj
    return character * (width - len(strObj)) + strObj


@Log.trace()
def count(strObj: str, subStr: str, start: int | None = None, end: int | None = None) -> int:
    """
    Counts occurrences of a substring within the string.

    Parameters:
        strObj: The string to search in.
        subStr: The substring to count.
        start: The starting index for the search. Default is None (start from the beginning).
        end: The ending index for the search. Default is None (search to the end).

    Returns:
        int: The number of occurrences of the substring.
    """
    return strObj.count(subStr, start, end)


@Log.trace()
def find_from_start(strObj: str, subStr: str, start: int | None = None, end: int | None = None) -> int:
    """
    Finds the first occurrence of a substring starting from the beginning of the string.

    Return -1 if the substring is not found.

    Parameters:
        strObj: The string to search in.
        subStr: The substring to find.
        start: The starting index for the search. Default is None (start from the beginning).
        end: The ending index for the search. Default is None (search to the end).

    Returns:
        int: The index of the first occurrence. Return -1 if the substring is not found.
    """
    return strObj.find(subStr, start, end)


@Log.trace()
def find_from_end(strObj: str, subStr: str, start: int | None = None, end: int | None = None) -> int:
    """
    Finds the last occurrence of a substring starting from the end of the string.

    Return -1 if the substring is not found.

    Parameters:
        strObj: The string to search in.
        subStr: The substring to find.
        start: The starting index for the search. Default is None (start from the beginning).
        end: The ending index for the search. Default is None (search to the end).

    Returns:
        int: The index of the last occurrence. Return -1 if the substring is not found.
    """
    return strObj.rfind(subStr, start, end)


@Log.trace()
def case_to_lower(strObj: str) -> str:
    """
    Converts all characters in the string to lowercase.

    Parameters:
        strObj: The string to convert.

    Returns:
        str: The string in lowercase.
    """
    return strObj.lower()


@Log.trace()
def case_to_upper(strObj: str) -> str:
    """
    Converts all characters in the string to uppercase.

    Parameters:
        strObj: The string to convert.

    Returns:
        str: The string in uppercase.
    """
    return strObj.upper()


@Log.trace()
def check_case_lower(strObj: str) -> bool:
    """
    Checks if all characters in the string are lowercase.

    Parameters:
        strObj: The string to check.

    Returns:
        bool: True if all characters are lowercase, False otherwise.
    """
    return strObj.islower()


@Log.trace()
def check_case_upper(strObj: str) -> bool:
    """
    Checks if all characters in the string are uppercase.

    Parameters:
        strObj: The string to check.

    Returns:
        bool: True if all characters are uppercase, False otherwise.
    """
    return strObj.isupper()


@Log.trace()
def case_swap(strObj: str) -> str:
    """
    Swaps the case of each character in the string.

    Parameters:
        strObj: The string to modify.

    Returns:
        str: The string with swapped cases.
    """
    return strObj.swapcase()


@Log.trace()
def strip(
    strObj: str, characters: list[str] | None = None, direction: Literal["start", "end", "both"] = "start"
) -> str:
    """
    Removes specified characters from the string based on the given direction.

    Parameters:
        strObj: The string to modify.
        characters: A list of characters to strip. If None, strips whitespace.
        direction: The direction to strip characters. Options are "start", "end", or "both". Default is "start".

    Returns:
        str: The modified string.
    """
    if isinstance(characters, list):
        for item in characters:
            if len(item) != 1:
                raise ValueError(f"The character '{item}' is not a one-length string.")
        character = "".join(characters)
    else:
        # None
        character = None

    """Note that all characters are independent, it's not a whole."""
    match direction:
        case "start":
            return strObj.lstrip(character)
        case "end":
            return strObj.rstrip(character)
        case "both":
            return strObj.strip(character)
        case _:
            raise ValueError(f'The argument direction({direction}) should be one of ["start", "end", "both"]')


@Log.trace()
def remove_prefix(strObj: str, prefix) -> str:
    """
    Removes a specified prefix from the beginning of a string if it exists.

    Parameters:
        strObj: The string from which to remove the prefix.
        prefix: The prefix to remove.

    Returns:
        str: The string after removing the specified prefix.
    """
    return strObj.removeprefix(prefix)


@Log.trace()
def remove_suffix(strObj: str, suffix) -> str:
    """
    Removes a specified suffix from the end of a string if it exists.

    Parameters:
        strObj: The string from which to remove the suffix.
        suffix: The suffix to remove.

    Returns:
        str: The string after removing the specified suffix.
    """
    return strObj.removesuffix(suffix)


@Log.trace()
def check_start(strObj: str, subStr: str) -> bool:
    """
    Checks if the string starts with the specified substring.

    Parameters:
        strObj: The string to check.
        subStr: The substring to look for at the start.

    Returns:
        bool: True if the string starts with subStr, False otherwise.
    """
    return strObj.startswith(subStr)


@Log.trace()
def check_end(strObj: str, subStr: str) -> bool:
    """
    Checks if the string ends with the specified substring.

    Parameters:
        strObj: The string to check.
        subStr: The substring to look for at the end.

    Returns:
        bool: True if the string ends with subStr, False otherwise.
    """
    return strObj.endswith(subStr)


@Log.trace()
def is_alpha_and_numeric(strObj: str) -> bool:
    """
    Checks if the string contains only alphanumeric characters.

    Parameters:
        strObj: The string to check.

    Returns:
        bool: True if the string is alphanumeric, False otherwise.
    """
    return strObj.isalnum()


@Log.trace()
def is_alpha(strObj: str) -> bool:
    """
    Checks if the string contains only alphabetic characters.

    Parameters:
        strObj: The string to check.

    Returns:
        bool: True if the string is alphabetic, False otherwise.
    """
    return strObj.isalpha()


@Log.trace()
def is_numeric(strObj: str) -> bool:
    """
    Checks if the string contains only numeric characters.

    Parameters:
        strObj: The string to check.

    Returns:
        bool: True if the string is numeric, False otherwise.
    """
    return strObj.isnumeric()


@Log.trace()
def is_ascii(strObj: str) -> bool:
    """
    Checks if the string is empty or all characters in the string are ASCII.

    Parameters:
        strObj: The string to check.

    Returns:
        bool: True if all characters are ASCII or the string is empty, False otherwise.
    """
    return strObj.isascii()


@Log.trace()
def is_digit(strObj: str) -> bool:
    """
    Checks if the string contains only digit characters.

    Parameters:
        strObj: The string to check.

    Returns:
        bool: True if the string is composed of digits, False otherwise.
    """
    return strObj.isdigit()


@Log.trace()
def is_decimal(strObj: str) -> bool:
    """
    Checks if the string represents a decimal number.

    Parameters:
        strObj: The string to check.

    Returns:
        bool: True if the string is a decimal number, False otherwise.
    """
    return strObj.isdecimal()


if __name__ == "__main__":

    # print(strip("  1122331  ", characters=None, direction="both"))
    # print(is_numeric("  112"))
    # print(split("123123123", "1", maxSplit=0))
    print(find_from_end(strObj="123321", subStr="1"))
