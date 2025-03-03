# FileName: List.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from typing import Any, TypeVar, Callable
import sys

T = TypeVar("T")
T2 = TypeVar("T2")


@Log.trace()
def insert(listObj: list[T], index: int, value: T) -> None:
    """
    Insert a value into a list at a specified index.

    Parameters:
        listObj: The list to modify.
        index: The index at which to insert the value.
        value: The value to insert.
    """
    listObj.insert(index, value)


@Log.trace()
def append(listObj: list[T], value: T) -> None:
    """
    Append a value to the end of a list.

    Parameters:
        listObj: The list to modify.
        value: The value to append.
    """
    listObj.append(value)


@Log.trace()
def pop(listObj: list[T], index: int = -1) -> T:
    """
    Remove and return an item from a list at a specified index.

    Parameters:
        listObj: The list to modify.
        index: The index of the item to remove. Default is -1 (last item).

    Returns:
        T: The removed item.
    """
    return listObj.pop(index)


@Log.trace()
def remove(listObj: list[T], value: T) -> None:
    """
    Remove the first occurrence of a value from a list.

    Parameters:
        listObj: The list to modify.
        value: The value to remove.
    """
    return listObj.remove(value)


@Log.trace()
def clear(listObj: list[Any]) -> None:
    """
    Clear all items from a list.

    Parameters:
        listObj: The list to clear.
    """
    listObj.clear()


@Log.trace()
def slice(listObj: list[T], start: int, end: int) -> list[T]:
    """
    Return a slice of the list between start and end indices.

    Parameters:
        listObj: The list to slice.
        start: The starting index of the slice.
        end: The ending index of the slice.

    Returns:
        list[T]: The sliced list.
    """
    return listObj[start:end]


@Log.trace()
def extend(listObj: list[T], listToExtend: list[T]) -> None:
    """
    Extend the list by appending elements from another list.

    Parameters:
        listObj: The list to modify.
        listToExtend: The list of elements to append.
    """
    listObj.extend(listToExtend)


@Log.trace()
def count(listObj: list[T], value: T) -> int:
    """
    Count occurrences of a value in the list.

    Parameters:
        listObj: The list to search.
        value: The value to count.

    Returns:
        int: The number of occurrences.
    """
    return listObj.count(value)


@Log.trace()
def find(listObj: list[T], value: T, start: int = 0, stop: int | None = None) -> int:
    """
    Return the first index of a value in the list.
    Raises ValueError if the value is not present.

    Parameters:
        listObj: The list to search.
        value: The value to find.
        start: The starting index for the search.
        stop: The ending index for the search. If it's None, use sys.maxsize

    Returns:
        int: The index of the value.
    """
    if stop is None:
        stop = sys.maxsize
    return listObj.index(value, start, stop)


@Log.trace()
def reverse(listObj: list[Any]) -> None:
    """
    Reverse the order of items in a list.

    Parameters:
        listObj: The list to reverse.
    """
    listObj.reverse()


@Log.trace()
def sort(listObj: list[Any], keyFunc: Callable | None = None, reverse: bool = False) -> None:
    """
    Sort the items in a list.

    Parameters:
        listObj: The list to sort.
        keyFunc: Optional function to specify the sort order.
        reverse: If True, sort in descending order.
    """
    listObj.sort(key=keyFunc, reverse=reverse)
