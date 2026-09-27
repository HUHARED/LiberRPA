# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from pydantic import BaseModel, ConfigDict

type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None


class JsonRequest(BaseModel):
    """Validate HTTP envelopes; application services own business validation."""

    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )


class JsonResponsePayload(BaseModel):
    """Describe public response fields without importing Django or its settings."""

    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )


class MessageResponse(JsonResponsePayload):
    message: str
