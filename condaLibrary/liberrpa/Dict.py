# FileName: Dict.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from typing import Any


@Log.trace()
def clear[K, V](dictObj: dict[K, V]) -> None:
    """
    Clear all items from the specified dictionary.

    Parameters:
        dictObj: The dictionary to clear.
    """
    dictObj.clear()


@Log.trace()
def get[K, V](dictObj: dict[K, V], key: K, default: V | None = None) -> V | None:
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
def pop[K, V](dictObj: dict[K, V], key: K, default: V | None = None) -> V | None:
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
def pop_item[K, V](dictObj: dict[K, V]) -> tuple[K, V]:
    """
    Remove and return the last inserted key-value pair from a dictionary.

    Parameters:
        dictObj: The dictionary to modify.

    Returns:
        tuple[T, T2]: The removed key-value pair.
    """
    return dictObj.popitem()


@Log.trace()
def get_key_list[K](dictObj: dict[K, Any]) -> list[K]:
    """
    Retrieve a list of keys from the specified dictionary.

    Parameters:
        dictObj: The dictionary from which to get the keys.

    Returns:
        list[T]: A list of keys in the dictionary.
    """
    return list(dictObj.keys())


@Log.trace()
def get_value_list[V](dictObj: dict[Any, V]) -> list[V]:
    """
    Retrieve a list of values from the specified dictionary.

    Parameters:
        dictObj: The dictionary from which to get the values.

    Returns:
        list[T]: A list of values in the dictionary.
    """
    return list(dictObj.values())


@Log.trace()
def extend[K, V](dictObj: dict[K, V], dictToExtend: dict[K, V]) -> None:
    """
    Extend a dictionary with the key-value pairs from another dictionary.

    Existing keys in dictObj are overwritten by values from dictToExtend.

    Parameters:
        dictObj: The dictionary to update in place.
        dictToExtend: The dictionary whose key-value pairs are added to dictObj.
    """
    dictObj.update(dictToExtend)
