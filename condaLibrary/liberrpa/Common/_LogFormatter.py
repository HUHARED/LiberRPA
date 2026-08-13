# FileName: _LogFormatter.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import logging
from collections.abc import Collection, Iterable


_STR_HUMAN_READ_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def build_human_read_format(
    *,
    includeProcessName: bool,
    includeSource: bool,
    customLogPart: Iterable[str] = (),
) -> str:
    listPart: list[str] = [
        "%(asctime)s",
        "%(levelname)s",
    ]

    if includeProcessName:
        listPart.append("%(processName)s")

    if includeSource:
        listPart.extend([
            "%(filename)s",
            "%(lineno)d",
        ])

    listPart.extend(f"%({strName})s" for strName in customLogPart)
    return "".join(f"[{strPart}]" for strPart in listPart) + " %(message)s"


class ConditionalHumanReadFormatter(logging.Formatter):
    def __init__(
        self,
        *,
        normalFormat: str,
        internalFormat: str,
        sourceHiddenFileNameSet: Collection[str],
    ) -> None:
        super().__init__()
        self.normalFormatter = logging.Formatter(
            normalFormat,
            datefmt=_STR_HUMAN_READ_DATE_FORMAT,
        )
        self.internalFormatter = logging.Formatter(
            internalFormat,
            datefmt=_STR_HUMAN_READ_DATE_FORMAT,
        )
        self.setSourceHiddenFileName = set(sourceHiddenFileNameSet)

    def format(self, record: logging.LogRecord) -> str:
        if record.filename in self.setSourceHiddenFileName:
            return self.internalFormatter.format(record)
        return self.normalFormatter.format(record)


def create_human_read_formatter(
    *,
    includeProcessName: bool,
    sourceHiddenFileNameSet: Collection[str] = (),
    customLogPart: Iterable[str] = (),
) -> logging.Formatter:
    tupleCustomLogPart = tuple(customLogPart)
    return ConditionalHumanReadFormatter(
        normalFormat=build_human_read_format(
            includeProcessName=includeProcessName,
            includeSource=True,
            customLogPart=tupleCustomLogPart,
        ),
        internalFormat=build_human_read_format(
            includeProcessName=includeProcessName,
            includeSource=False,
            customLogPart=tupleCustomLogPart,
        ),
        sourceHiddenFileNameSet=sourceHiddenFileNameSet,
    )
