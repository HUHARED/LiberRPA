# FileName: Time.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import time
from datetime import datetime, timedelta
from typing import Literal

@Log.trace()
def get_unix_time() -> float:
    """
    Returns the current time in Unix timestamp format.

    Returns:
        float: The current time in seconds since the epoch (January 1, 1970).
    """
    return time.time()


@Log.trace()
def get_datetime_now() -> datetime:
    """
    Returns the current local date and time.

    Returns:
        datetime: The current local date and time.
    """
    return datetime.now()


@Log.trace()
def build_datetime(
    year: int = 1984,
    month: int = 4,
    day: int = 4,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
) -> datetime:
    """
    Builds a datetime object from the provided components.

    Parameters:
        year: Year of the datetime.
        month: Month of the datetime.
        day: Day of the datetime.
        hour: Hour of the datetime.
        minute: Minute of the datetime.
        second: Second of the datetime.
        microsecond: Microsecond of the datetime.

    Returns:
        datetime: The constructed datetime object.
    """
    return datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second, microsecond=microsecond)


@Log.trace()
def str_to_datetime(strObj: str, format: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    Converts a string representation of a date and time into a datetime object.
    
    Check the format codes in [strftime() and strptime() Format Codes]( https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes)

    Parameters:
        strObj: The string representation of the date and time.
        format: The format of the string.

    Returns:
        datetime: The corresponding datetime object.
    """
    return datetime.strptime(strObj, format)


@Log.trace()
def datetime_to_str(datetimeObj: datetime, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Converts a datetime object into a string representation.
    
    Check the format codes in [strftime() and strptime() Format Codes]( https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes)

    Parameters:
        datetimeObj: The datetime object to convert.
        format: The format for the output string (default is "%Y-%m-%d %H:%M:%S").

    Returns:
        str: The string representation of the datetime object.
    """
    return datetimeObj.strftime(format)

@Log.trace()
def get_datetime_attr(datetimeObj: datetime,attr:Literal["year","month","day","hour","minute","second","millisecond","microsecond"]) -> int:
    """
    Retrieves a specific attribute from a datetime object.

    Parameters:
        datetimeObj: The datetime object from which to retrieve the attribute.
        attr: The attribute to retrieve (one of "year", "month", "day", "hour", "minute", "second", "millisecond", "microsecond").

    Returns:
        int: The value of the requested attribute.
    """
    match attr:
        case "year":
            return datetimeObj.year
        case "month":
            return datetimeObj.month
        case "day":
            return datetimeObj.day
        case "hour":
            return datetimeObj.hour
        case "minute":
            return datetimeObj.minute
        case "second":
            return datetimeObj.second
        case "millisecond":
            return datetimeObj.microsecond//1000
        case "microsecond":
            return datetimeObj.microsecond
        case _:
            raise ValueError(f"The argument attr should be one of {["year","month","day","hour","minute","second","millisecond","microsecond"]}")

@Log.trace()
def add_datetime(
    datetimeObj: datetime,
    week: int = 0,
    day: int = 0,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    millisecond:int=0,
    microsecond: int = 0,
) -> datetime:
    """
    Adds a specified amount of time to a datetime object.

    Parameters:
        datetimeObj: The original datetime object.
        week: Number of weeks to addfraction.
        day: Number of days to addfraction.
        hour: Number of hours to addfraction.
        minute: Number of minutes to addfraction.
        second: Number of seconds to addfraction.
        millisecond: Number of milliseconds to addfraction.
        microsecond: Number of microseconds to addfraction.

    Returns:
        datetime: The new datetime object after adding the specified time.
    """
    return datetimeObj+timedelta(weeks=week,  days=day, hours=hour, minutes=minute, seconds=second, milliseconds=millisecond,microseconds=microsecond)


if __name__ == "__main__":
    dt = datetime.now()

    # print(get_datetime_attr(datetimeObj=dt,attr="microsecond"))
    # print(get_datetime_attr(datetimeObj=dt,attr="millisecond"))
    print(add_datetime(dt,millisecond=1000))
