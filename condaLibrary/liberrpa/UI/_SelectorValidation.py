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
    DictSepcImage,
    SelectorWindow,
    SelectorUia,
    SelectorHtml,
    SelectorImage,
)
import re
from typing import cast, Any


def as_selector_uia(selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage) -> SelectorUia:
    if selector.get("category") != "uia":
        raise UiSelectorError(f"Expected SelectorUia, got selector category: {selector.get('category')!r}")
    return cast(SelectorUia, selector)


def as_selector_html(selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage) -> SelectorHtml:
    if selector.get("category") != "html":
        raise UiSelectorError(f"Expected SelectorHtml, got selector category: {selector.get('category')!r}")
    return cast(SelectorHtml, selector)


def as_selector_image(selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage) -> SelectorImage:
    if selector.get("category") != "image":
        raise UiSelectorError(f"Expected SelectorImage, got selector category: {selector.get('category')!r}")
    return cast(SelectorImage, selector)


_ALLOWED_SELECTOR_ROOT_KEYS = {"window", "category", "specification"}
_ALLOWED_WINDOW_KEYS = set(getattr(DictSpecWindow, "__annotations__", {}))
_ALLOWED_UIA_SPEC_KEYS = set(getattr(DictSpecUia, "__annotations__", {}))
_ALLOWED_HTML_SPEC_KEYS = set(getattr(DictSpecHtml, "__annotations__", {}))
_ALLOWED_IMAGE_SPEC_KEYS = set(getattr(DictSepcImage, "__annotations__", {}))

_UIA_INT_TEXT_KEYS = {"Depth", "Index"}

_HTML_INT_TEXT_KEYS = {"tableRowIndex", "tableColumnIndex", "childIndex", "documentIndex"}
_HTML_BOOL_TEXT_KEYS = {"disabled", "isHidden", "isDisplayedNone", "isLeaf"}
_HTML_TRISTATE_TEXT_KEYS = {"checked"}

_IMAGE_INT_TEXT_KEYS = {"Index"}
_IMAGE_FLOAT_TEXT_KEYS = {"Confidence"}
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


def _validate_int_text_items(dictObj: dict[str, object], keys: set[str], selectorPartName: str) -> None:
    for key in keys:
        value = _get_optional_str(dictObj=dictObj, key=key, selectorPartName=selectorPartName)
        if value is None:
            continue

        try:
            int(value)
        except ValueError as e:
            raise UiSelectorError(f"{selectorPartName}.{key} should be a valid integer string.") from e


def _validate_float_text_items(dictObj: dict[str, object], keys: set[str], selectorPartName: str) -> None:
    for key in keys:
        value = _get_optional_str(dictObj=dictObj, key=key, selectorPartName=selectorPartName)
        if value is None:
            continue

        try:
            float(value)
        except ValueError as e:
            raise UiSelectorError(f"{selectorPartName}.{key} should be a valid float string.") from e


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
        keys=_UIA_INT_TEXT_KEYS,
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
                    keys=_UIA_INT_TEXT_KEYS,
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
                    keys=_HTML_INT_TEXT_KEYS,
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
                keys=_IMAGE_INT_TEXT_KEYS,
                selectorPartName="selector.specification[0]",
            )
            _validate_float_text_items(
                dictObj=specDict,
                keys=_IMAGE_FLOAT_TEXT_KEYS,
                selectorPartName="selector.specification[0]",
            )
            _validate_text_value_items(
                dictObj=specDict,
                keys=_IMAGE_BOOL_TEXT_KEYS,
                allowedValues=_BOOL_TEXT_VALUES,
                selectorPartName="selector.specification[0]",
            )
