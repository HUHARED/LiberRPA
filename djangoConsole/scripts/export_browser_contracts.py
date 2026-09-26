# FileName: export_browser_contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import argparse
import json
from pathlib import Path
import sys

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaMode, JsonSchemaValue, models_json_schema

_PATH_CONSOLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PATH_CONSOLE / "backend"))

from accounts.contracts import LoginRequest, SessionResponse, CsrfResponse
from console_project.contracts import MessageResponse
from executors.contracts import (
    ExecutorUpdateRequest,
    ExecutorDispatchRequest,
    ExecutorUnassociateRequest,
    ExecutorUpdateResponse,
    ExecutorListResponse,
    ExecutorDetailsResponse,
)
from organizations.contracts import AccountAccessResponse

_TUPLE_CONTRACT_MODEL: tuple[tuple[type[BaseModel], JsonSchemaMode], ...] = (
    (LoginRequest, "validation"),
    (CsrfResponse, "serialization"),
    (SessionResponse, "serialization"),
    (AccountAccessResponse, "serialization"),
    (MessageResponse, "serialization"),
    (ExecutorListResponse, "serialization"),
    (ExecutorDetailsResponse, "serialization"),
    (ExecutorUpdateRequest, "validation"),
    (ExecutorDispatchRequest, "validation"),
    (ExecutorUnassociateRequest, "validation"),
    (ExecutorUpdateResponse, "serialization"),
)


def build_browser_contract_schema() -> JsonSchemaValue:
    """Export only public browser payloads, without settings, secrets or a database."""
    dictReference, dictSchema = models_json_schema(_TUPLE_CONTRACT_MODEL)
    dictSchema.update({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "BrowserApiContracts",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            contractModel.__name__: dictReference[(contractModel, strMode)]
            for contractModel, strMode in _TUPLE_CONTRACT_MODEL
        },
        "required": [
            contractModel.__name__ for contractModel, _ in _TUPLE_CONTRACT_MODEL
        ],
    })
    return dictSchema


def main() -> int:
    argumentParser = argparse.ArgumentParser(
        description="Export browser API schemas, or check the committed schema without changing it."
    )
    argumentParser.add_argument("--check", action="store_true")
    arguments = argumentParser.parse_args()
    boolCheck = bool(arguments.check)
    pathSchema = _PATH_CONSOLE / "frontend/contracts/browser-api.schema.json"
    strExpected = (
        json.dumps(build_browser_contract_schema(), indent=2, sort_keys=True) + "\n"
    )
    if boolCheck:
        if (
            not pathSchema.is_file()
            or pathSchema.read_text(encoding="utf-8") != strExpected
        ):
            print(
                "Browser API schema is out of date. Run python scripts/export_browser_contracts.py.",
                file=sys.stderr,
            )
            return 1
    else:
        pathSchema.parent.mkdir(parents=True, exist_ok=True)
        pathSchema.write_text(strExpected, encoding="utf-8", newline="\n")
    if boolCheck:
        print("Browser API schema matches backend contracts.")
    else:
        print(
            "Browser API schema exported. Run npm run generate:contracts in frontend next."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
