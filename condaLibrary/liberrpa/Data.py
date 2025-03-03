# FileName: Data.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from pathvalidate import sanitize_filename as _sanitize_filename
from decimal import Decimal
from copy import deepcopy
from typing import Literal, Any, TypeVar, Iterable
import uuid
import random
import json

T = TypeVar("T")
T2 = TypeVar("T2")


@Log.trace()
def sanitize_filename(filename: str) -> str:
    """
    Sanitize a given filename using the pathvalidate module.

    Parameters:
        filename: The original filename to sanitize.

    Returns:
        str: The sanitized filename.
    """
    strNew = _sanitize_filename(filename=filename)
    if strNew != filename:
        Log.warning(f"The original filename({filename}) has been sanitized to '{strNew}'")

    # If sanitization results in an empty filename, raise an exception
    if not strNew:
        raise ValueError(f"The filename '{filename}' is invalid after sanitization.")

    return strNew


@Log.trace()
def get_length(value: str | bytes | list | tuple | range | dict | set | frozenset) -> int:
    """
    Get the length of the given value.

    Parameters:
        value: The value whose length is to be measured.

    Returns:
        int: The length of the value.
    """
    return len(value)


@Log.trace()
def to_integer(value: str | float | bool | bytes | int) -> int:
    """
    Convert the given value to an integer.

    Parameters:
        value: The value to convert.

    Returns:
        int: The converted integer value.
    """
    return int(value)


@Log.trace()
def to_float(value: str | bool | bytes | int | float) -> float:
    """
    Convert the given value to a float.

    Parameters:
        value: The value to convert.

    Returns:
        float: The converted float value.
    """
    return float(value)


@Log.trace()
def to_decimal(value: str | int | float | tuple[Literal[0, 1], tuple[int, ...], int] | Decimal) -> Decimal:
    """
    Convert the given value to a Decimal.

    Parameters:
        value: The value to convert.

    Returns:
        Decimal: The converted decimal value.
    """
    return Decimal(value)


@Log.trace()
def to_boolean(value) -> bool:
    """
    Convert the given value to a boolean.

    Parameters:
        value: The value to convert.

    Returns:
        bool: The converted boolean value.
    """
    return bool(value)


@Log.trace()
def clone(value: T) -> T:
    """
    Create a deep copy of the given value.

    Parameters:
        value: The value to clone.

    Returns:
        T: The cloned value.
    """
    return deepcopy(value)


@Log.trace()
def get_type(value: Any) -> str:
    """
    Get the type name of the given value.

    Parameters:
        value: The value whose type is to be identified.

    Returns:
        str: The type name of the value.
    """
    return type(value).__name__


@Log.trace()
def get_uuid() -> str:
    """
    Generate a new UUID.

    Returns:
        str: The generated UUID as a string.
    """
    return str(uuid.uuid4())


@Log.trace()
def get_random_integer(start: int, end: int) -> int:
    """
    Return a random integer in the range [start, end].

    Parameters:
        start: The start of the range.
        end: The end of the range.

    Returns:
        int: A random integer within the specified range.
    """
    return random.randint(start, end)


@Log.trace()
def get_random_float(start: float | None = None, end: float | None = None) -> float:
    """
    Generate a random float in the specified range.

    Parameters:
        start: The start of the range, or None for [0.0, 1.0).
        end: The end of the range, or None for [0.0, 1.0).

    Returns:
        float: A random float within the specified range.
    """
    if start is None and end == None:
        return random.random()
    elif isinstance(start, float) and isinstance(end, float):
        return random.uniform(start, end)
    else:
        raise ValueError("The argument start and end cannot be None both.")


@Log.trace()
def json_dumps(value: Any, indent: int = 4) -> str:
    """
    Serialize an object to a JSON formatted string.

    Parameters:
        value: The object to serialize.
        indent: The number of spaces to use for indentation.

    Returns:
        str: The JSON formatted string.
    """
    return json.dumps(obj=value, indent=indent)


@Log.trace()
def json_loads(jsonStr: str) -> Any:
    """
    Deserialize a JSON formatted string to a Python object.

    Parameters:
        jsonStr: The JSON string to deserialize.

    Returns:
        Any: The deserialized Python object.
    """
    return json.loads(jsonStr)


@Log.trace()
def join_to_str(iterableObj: Iterable[str], joinStr: str = ",") -> str:
    """
    Join a list of strings into a single string with a specified separator.

    Parameters:
        iterableObj: The iterable value of strings to join.
        joinStr: The string used to separate the joined strings.

    Returns:
        str: The joined string.
    """
    return joinStr.join(iterableObj)


if __name__ == "__main__":
    ...
