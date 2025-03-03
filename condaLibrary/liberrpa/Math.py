# FileName: Math.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from builtins import round as _round
import math
from decimal import Decimal
from typing import TypeVar

number = TypeVar("number", int, float, Decimal)


@Log.trace()
def round(value: number, fraction: int = 0) -> number:
    """
    Rounds a number to a specified precision in fractional digits.
    fraction may be negative.

    Parameters:
        value: The number to be rounded (int, float, or Decimal).
        fraction: The number of decimal places to round to. Can be negative.

    Returns:
        The rounded value, with the same type as the input number.
    """
    return _round(value, fraction)  # type: ignore


@Log.trace()
def check_float_equal(value1: float, value2: float) -> bool:
    """
    Checks if two floating-point numbers are approximately equal.

    Parameters:
        value1: The first float to compare.
        value2: The second float to compare.

    Returns:
        True if the values are close, False otherwise.
    """
    return math.isclose(value1, value2)


@Log.trace()
def absolute(value: number) -> number:
    """
    Computes the absolute value of a number.

    Parameters:
        value: The number for which to compute the absolute value.

    Returns:
        The absolute value of the input number.
    """
    return abs(value)  # type: ignore


@Log.trace()
def get_int_and_fraction(value: number) -> tuple[int, float]:
    """
    Splits a number into its integer and fractional parts.

    Parameters:
        value: The number to split (int, float, or Decimal).

    Returns:
        tuple[int, float]: A tuple containing the integer part and the fractional part.
    """
    fractionPart, intPart = math.modf(value)
    return (int(intPart), fractionPart)


if __name__ == "__main__":
    # temp = 1123.1
    # temp2 = round(temp)
    print(abs(Decimal(-123.1)))
    print(abs(Decimal(-123)))
    print(absolute(Decimal(-123.1)))
    print(type(absolute(Decimal(-123.1))))
