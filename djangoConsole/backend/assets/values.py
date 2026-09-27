# FileName: values.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from console_project.contracts import JsonValue
from console_project.validators import validate_json_value

from .models import AssetType, SECRET_ASSET_TYPES


@sensitive_variables()
def serialize_asset_value(assetType: str, value: JsonValue) -> str:
    """Validate one value once and return its canonical storage representation."""
    try:
        match assetType:
            case AssetType.TEXT | AssetType.SECRET_TEXT:
                if not isinstance(value, str):
                    raise ValueError("Enter a text value.")
            case AssetType.INTEGER:
                if type(value) is not int:
                    raise ValueError("Enter an integer.")
            case AssetType.NUMBER:
                if type(value) not in (int, float):
                    raise ValueError("Enter a number.")
            case AssetType.BOOLEAN:
                if type(value) is not bool:
                    raise ValueError("Select true or false.")
            case AssetType.CREDENTIAL:
                if (
                    not isinstance(value, dict)
                    or set(value) != {"username", "password"}
                    or not all(isinstance(part, str) for part in value.values())
                ):
                    raise ValueError(
                        "Provide the complete Username and Password as text."
                    )
            case AssetType.JSON:
                pass
            case _:
                raise ValueError("Select a supported asset type.")
        validate_json_value(value)
        strJson = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
        intLimit = (
            limits.maxSecretAssetValueBytes
            if assetType in SECRET_ASSET_TYPES
            else limits.maxAssetValueBytes
        )
        intValueBytes = len(
            (value if isinstance(value, str) else strJson).encode("utf-8")
        )
        if intValueBytes > intLimit:
            raise ValueError(f"The value exceeds the {intLimit}-byte UTF-8 limit.")
        return strJson
    except (ValueError, RecursionError) as e:
        raise ValidationError({
            "value": str(e)
            if not isinstance(e, (UnicodeError, RecursionError))
            else "Enter valid Unicode JSON within 64 levels of nesting."
        }) from None
