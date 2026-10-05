# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from pydantic import Field

from console_project.contracts import JsonRequest


class RecipientCreationRequest(JsonRequest):
    email: str = Field(min_length=1, max_length=254)
    notes: str = Field(default="", max_length=2000)


class RecipientNotesRequest(JsonRequest):
    notes: str = Field(max_length=2000)


class EmptyRequest(JsonRequest):
    pass


class RecipientTokenRequest(JsonRequest):
    token: str = Field(min_length=1, max_length=1000)
