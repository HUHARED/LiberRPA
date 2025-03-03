# FileName: Dict.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from typing import Any, TypeVar

T = TypeVar("T")
T2 = TypeVar("T2")


@Log.trace()
def clear(dictObj: dict) -> None:
    """
    Clear all items from the specified dictionary.

    Parameters:
        dictObj: The dictionary to clear.
    """
    dictObj.clear()


@Log.trace()
def get(dictObj: dict[T, T2], key: T, default: T2 | None = None) -> T2 | None:
    """
    Retrieve the value associated with a specified key from the dictionary.
    
    If the key is not found, return the default.

    Parameters:
        dictObj: The dictionary to search.
        key: The key whose value is to be retrieved.
        default: The value to return if the key is not found.

    Returns:
        T2 | None: The value associated with the key or the default value if not found.
    """
    return dictObj.get(key, default)


@Log.trace()
def pop(dictObj: dict[T, T2], key: T, default: T2 | None = None) -> T2 | None:
    """
    Remove a specified key from the dictionary and return its corresponding value.
    
    If the key is not found, return the default.

    Parameters:
        dictObj: The dictionary to modify.
        key: The key to remove from the dictionary.
        default: The value to return if the key is not found.

    Returns:
        T2 | None: The value associated with the removed key or the default value if not found.
    """
    return dictObj.pop(key, default)


@Log.trace()
def pop_item(dictObj: dict[T, T2]) -> tuple[T, T2]:
    """
    Remove a specified key from the dictionary and return its corresponding value.
    
    Raise KeyError if dictObj is empty.

    Parameters:
        dictObj: The dictionary to modify.
        key: The key to remove from the dictionary.
        default: The value to return if the key is not found.

    Returns:
        T2 | None: The value associated with the removed key or the default value if not found.
    """
    return dictObj.popitem()


@Log.trace()
def get_key_list(dictObj: dict[T, Any]) -> list[T]:
    """
    Retrieve a list of keys from the specified dictionary.

    Parameters:
        dictObj: The dictionary from which to get the keys.

    Returns:
        list[T]: A list of keys in the dictionary.
    """
    return list(dictObj.keys())


@Log.trace()
def get_value_list(dictObj: dict[Any, T]) -> list[T]:
    """
    Retrieve a list of values from the specified dictionary.

    Parameters:
        dictObj: The dictionary from which to get the values.

    Returns:
        list[T]: A list of values in the dictionary.
    """
    return list(dictObj.values())


@Log.trace()
def extend(dictObj: dict[T, T2], dictToExtend: dict[T, T2]) -> None:
    """
    Retrieve a list of values from the specified dictionary.

    Parameters:
        dictObj: The dictionary from which to get the values.

    Returns:
        list[T]: A list of values in the dictionary.
    """
    dictObj.update(dictToExtend)
