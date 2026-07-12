# FileName: _SelectorValidation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.Common._Exception import UiSelectorError
from liberrpa.UI._UiDict import (
    DictSpecWindow,
    DictSpecUia,
    DictSpecHtml,
    DictSpecImage,
    SelectorWindow,
    SelectorUia,
    SelectorHtml,
    SelectorImage,
    Selector,
)

import re
import math
from typing import Any, cast
from collections.abc import Mapping


_ALLOWED_SELECTOR_ROOT_KEYS = {"window", "category", "specification"}
_ALLOWED_WINDOW_KEYS = set(getattr(DictSpecWindow, "__annotations__", {}))
_ALLOWED_UIA_SPEC_KEYS = set(getattr(DictSpecUia, "__annotations__", {}))
_ALLOWED_HTML_SPEC_KEYS = set(getattr(DictSpecHtml, "__annotations__", {}))
_ALLOWED_IMAGE_SPEC_KEYS = set(getattr(DictSpecImage, "__annotations__", {}))

type IntRange = tuple[int | None, int | None]
type FloatRange = tuple[float | None, float | None]

_WINDOW_INT_TEXT_RULES: Mapping[str, IntRange] = {
    "Index": (0, None),
}

_UIA_INT_TEXT_RULES: Mapping[str, IntRange] = {
    "Depth": (1, None),
    "Index": (0, None),
}

_HTML_INT_TEXT_RULES: Mapping[str, IntRange] = {
    "tableRowIndex": (0, None),
    "tableColumnIndex": (0, None),
    "childIndex": (0, None),
    "documentIndex": (0, None),
}
_HTML_BOOL_TEXT_KEYS = {"disabled", "isHidden", "isDisplayedNone", "isLeaf"}
_HTML_TRISTATE_TEXT_KEYS = {"checked"}

_IMAGE_INT_TEXT_RULES: Mapping[str, IntRange] = {"Index": (0, None)}
_IMAGE_FLOAT_TEXT_RULES: Mapping[str, FloatRange] = {"Confidence": (0.0, 1.0)}
_IMAGE_BOOL_TEXT_KEYS = {"Grayscale"}

_BOOL_TEXT_VALUES = {"true", "false"}
_TRISTATE_TEXT_VALUES = {"true", "false", "indeterminate"}


def _validate_allowed_keys(dictObj: dict[str, object], allowedKeys: set[str], selectorPartName: str) -> None:
    listInvalidKeys = sorted(set(dictObj) - allowedKeys)
    if listInvalidKeys:
        raise UiSelectorError(f"{selectorPartName} contains unsupported keys: {listInvalidKeys}")


def _validate_values_are_str(dictObj: dict[str, object], selectorPartName: str) -> None:
    for key, value in dictObj.items():
        if not isinstance(value, str):
            raise UiSelectorError(f"{selectorPartName}.{key} should be a string, got {type(value).__name__}: {value!r}")


def _validate_regex_items(dictObj: dict[str, Any], selectorPartName: str) -> None:
    for key, value in dictObj.items():
        if not key.endswith("-regex"):
            continue

        if not isinstance(value, str):
            raise UiSelectorError(f"{selectorPartName}.{key} should be a regex string, got {type(value).__name__}.")

        try:
            re.compile(value)
        except re.error as e:
            raise UiSelectorError(f"Invalid regex in {selectorPartName}.{key}: {value!r}. Error: {e}") from e


def _validate_exact_regex_conflict(dictObj: dict[str, object], selectorPartName: str) -> None:
    for key in dictObj:
        if not key.endswith("-regex"):
            continue

        exactKey = key.removesuffix("-regex")
        if exactKey in dictObj:
            raise UiSelectorError(f"{selectorPartName} should not contain both {exactKey!r} and {key!r}.")


def _validate_selector_part(
    dictObj: object,
    allowedKeys: set[str],
    selectorPartName: str,
    requiredKeys: set[str] | None = None,
) -> dict[str, object]:

    if not isinstance(dictObj, dict):
        raise UiSelectorError(f"{selectorPartName} should be a dictionary, got {type(dictObj).__name__}.")

    requiredKeys = set() if requiredKeys is None else requiredKeys
    listMissingKeys = sorted(requiredKeys - set(dictObj))
    if listMissingKeys:
        raise UiSelectorError(f"{selectorPartName} is missing required keys: {listMissingKeys}")

    _validate_allowed_keys(dictObj=dictObj, allowedKeys=allowedKeys, selectorPartName=selectorPartName)
    _validate_values_are_str(dictObj=dictObj, selectorPartName=selectorPartName)
    _validate_regex_items(dictObj=dictObj, selectorPartName=selectorPartName)
    _validate_exact_regex_conflict(dictObj=dictObj, selectorPartName=selectorPartName)

    return dictObj


def _get_optional_str(dictObj: dict[str, object], key: str, selectorPartName: str) -> str | None:
    value = dictObj.get(key)

    if value is None:
        return None

    if not isinstance(value, str):
        raise UiSelectorError(f"{selectorPartName}.{key} should be a string, got {type(value).__name__}: {value!r}")

    return value


def _format_number_range(minValue: int | float | None, maxValue: int | float | None) -> str:
    if minValue is not None and maxValue is not None:
        return f"between {minValue} and {maxValue}"
    if minValue is not None:
        return f">= {minValue}"
    if maxValue is not None:
        return f"<= {maxValue}"
    return ""


def _validate_int_text_items(
    dictObj: dict[str, object],
    rules: Mapping[str, IntRange],
    selectorPartName: str,
) -> None:
    for key, (minValue, maxValue) in rules.items():
        value = _get_optional_str(dictObj=dictObj, key=key, selectorPartName=selectorPartName)
        if value is None:
            continue

        try:
            intValue = int(value)
        except ValueError as e:
            raise UiSelectorError(f"{selectorPartName}.{key} should be a valid integer string, got {value!r}.") from e

        if minValue is not None and intValue < minValue:
            raise UiSelectorError(
                f"{selectorPartName}.{key} should be an integer string {_format_number_range(minValue, maxValue)}, got {value!r}."
            )

        if maxValue is not None and intValue > maxValue:
            raise UiSelectorError(
                f"{selectorPartName}.{key} should be an integer string {_format_number_range(minValue, maxValue)}, got {value!r}."
            )


def _validate_float_text_items(
    dictObj: dict[str, object],
    rules: Mapping[str, FloatRange],
    selectorPartName: str,
) -> None:
    for key, (minValue, maxValue) in rules.items():
        value = _get_optional_str(dictObj=dictObj, key=key, selectorPartName=selectorPartName)
        if value is None:
            continue

        try:
            floatValue = float(value)
        except ValueError as e:
            raise UiSelectorError(f"{selectorPartName}.{key} should be a valid float string, got {value!r}.") from e

        if not math.isfinite(floatValue):
            raise UiSelectorError(
                f"{selectorPartName}.{key} should be a finite float string {_format_number_range(minValue, maxValue)}, got {value!r}."
            )

        if minValue is not None and floatValue < minValue:
            raise UiSelectorError(
                f"{selectorPartName}.{key} should be a float string {_format_number_range(minValue, maxValue)}, got {value!r}."
            )

        if maxValue is not None and floatValue > maxValue:
            raise UiSelectorError(
                f"{selectorPartName}.{key} should be a float string {_format_number_range(minValue, maxValue)}, got {value!r}."
            )


def _validate_text_value_items(
    dictObj: dict[str, object],
    keys: set[str],
    allowedValues: set[str],
    selectorPartName: str,
) -> None:
    for key in keys:
        value = _get_optional_str(dictObj=dictObj, key=key, selectorPartName=selectorPartName)
        if value is None:
            continue

        if value not in allowedValues:
            raise UiSelectorError(f"{selectorPartName}.{key} should be one of {sorted(allowedValues)}, got {value!r}.")


def validate_selector(selector: object) -> None:
    """
    Validate selector structure.

    Raises:
        UiSelectorError: If the selector structure is invalid.
    """

    if not isinstance(selector, dict):
        raise UiSelectorError(f"selector should be a dictionary, got {type(selector).__name__}.")

    _validate_allowed_keys(
        dictObj=selector,
        allowedKeys=_ALLOWED_SELECTOR_ROOT_KEYS,
        selectorPartName="selector",
    )

    if "window" not in selector:
        raise UiSelectorError("selector should contain key 'window'.")

    windowPart = _validate_selector_part(
        dictObj=selector["window"],
        allowedKeys=_ALLOWED_WINDOW_KEYS,
        selectorPartName="selector.window",
        requiredKeys={"ControlTypeName"},
    )

    _validate_int_text_items(
        dictObj=windowPart,
        rules=_WINDOW_INT_TEXT_RULES,
        selectorPartName="selector.window",
    )
    category = selector.get("category")

    if category is None:
        # Window selector.
        if "specification" in selector:
            raise UiSelectorError("Window selector should not contain key 'specification'.")
        return None

    if category not in ("uia", "html", "image"):
        raise UiSelectorError(f"selector['category'] should be one of ['uia', 'html', 'image'], got {category!r}.")

    specification = selector.get("specification")
    if not isinstance(specification, list) or len(specification) == 0:
        raise UiSelectorError("selector['specification'] should be a non-empty list.")

    match category:
        case "uia":
            for index, specPart in enumerate(specification):
                specDict = _validate_selector_part(
                    dictObj=specPart,
                    allowedKeys=_ALLOWED_UIA_SPEC_KEYS,
                    selectorPartName=f"selector.specification[{index}]",
                    requiredKeys={"ControlTypeName"},
                )

                selectorPartName = f"selector.specification[{index}]"
                _validate_int_text_items(
                    dictObj=specDict,
                    rules=_UIA_INT_TEXT_RULES,
                    selectorPartName=selectorPartName,
                )

        case "html":
            for index, specPart in enumerate(specification):
                specDict = _validate_selector_part(
                    dictObj=specPart,
                    allowedKeys=_ALLOWED_HTML_SPEC_KEYS,
                    selectorPartName=f"selector.specification[{index}]",
                )

                selectorPartName = f"selector.specification[{index}]"

                _validate_int_text_items(
                    dictObj=specDict,
                    rules=_HTML_INT_TEXT_RULES,
                    selectorPartName=selectorPartName,
                )
                _validate_text_value_items(
                    dictObj=specDict,
                    keys=_HTML_BOOL_TEXT_KEYS,
                    allowedValues=_BOOL_TEXT_VALUES,
                    selectorPartName=selectorPartName,
                )
                _validate_text_value_items(
                    dictObj=specDict,
                    keys=_HTML_TRISTATE_TEXT_KEYS,
                    allowedValues=_TRISTATE_TEXT_VALUES,
                    selectorPartName=selectorPartName,
                )

        case "image":
            if len(specification) != 1:
                raise UiSelectorError("Image selector should contain exactly one specification layer.")

            specDict = _validate_selector_part(
                dictObj=specification[0],
                allowedKeys=_ALLOWED_IMAGE_SPEC_KEYS,
                selectorPartName="selector.specification[0]",
                requiredKeys={"FileName", "Grayscale", "Confidence"},
            )

            _validate_int_text_items(
                dictObj=specDict,
                rules=_IMAGE_INT_TEXT_RULES,
                selectorPartName="selector.specification[0]",
            )
            _validate_float_text_items(
                dictObj=specDict,
                rules=_IMAGE_FLOAT_TEXT_RULES,
                selectorPartName="selector.specification[0]",
            )
            _validate_text_value_items(
                dictObj=specDict,
                keys=_IMAGE_BOOL_TEXT_KEYS,
                allowedValues=_BOOL_TEXT_VALUES,
                selectorPartName="selector.specification[0]",
            )


def ensure_selector(value: object) -> Selector:
    validate_selector(selector=value)
    return cast(Selector, value)


def ensure_selector_window(value: object) -> SelectorWindow:
    selector = ensure_selector(value)

    if selector.get("category") is None:
        return cast(SelectorWindow, selector)

    raise UiSelectorError(f"Expected SelectorWindow, got selector category: {selector.get('category')!r}.")


def ensure_selector_uia(value: object) -> SelectorUia:
    selector = ensure_selector(value)

    if selector.get("category") == "uia":
        return cast(SelectorUia, selector)

    raise UiSelectorError(f"Expected SelectorUia, got selector category: {selector.get('category')!r}.")


def ensure_selector_html(value: object) -> SelectorHtml:
    selector = ensure_selector(value)

    if selector.get("category") == "html":
        return cast(SelectorHtml, selector)

    raise UiSelectorError(f"Expected SelectorHtml, got selector category: {selector.get('category')!r}.")


def ensure_selector_image(value: object) -> SelectorImage:
    selector = ensure_selector(value)

    if selector.get("category") == "image":
        return cast(SelectorImage, selector)

    raise UiSelectorError(f"Expected SelectorImage, got selector category: {selector.get('category')!r}.")
