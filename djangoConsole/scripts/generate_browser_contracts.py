# FileName: generate_browser_contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import argparse
import json
from pathlib import Path
import subprocess
import sys

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaMode, JsonSchemaValue, models_json_schema

_PATH_CONSOLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PATH_CONSOLE / "backend"))

from accounts.contracts import (
    LoginRequest,
    SessionResponse,
    CsrfResponse,
    AccountDeletionRequest,
    AccountDeletionPreviewResponse,
)
from console_project.contracts import MessageResponse
from executors.contracts import (
    ExecutorUpdateRequest,
    ExecutorCreationRequest,
    ExecutorDeletionRequest,
    ExecutorDispatchRequest,
    ExecutorUnassociateRequest,
    ExecutorUpdateResponse,
    ExecutorListResponse,
    ExecutorDetailsResponse,
    ExecutorGroupUpdateRequest,
    ExecutorGroupCreationRequest,
    ExecutorGroupDeletionRequest,
    ExecutorGroupListResponse,
    ExecutorGroupDetailsResponse,
    ExecutorGroupDeletionResponse,
    ExecutorGroupWriteResponse,
)
from organizations.contracts import (
    AccountAccessResponse,
    DepartmentUpdateRequest,
    DepartmentCreationRequest,
    DepartmentDeletionRequest,
    DepartmentWriteResponse,
    DepartmentListResponse,
    DepartmentDetailsResponse,
    DepartmentDeletionPreviewResponse,
    DepartmentDeletionResponse,
    MemberListResponse,
    MemberDetailsResponse,
    MembershipUpdateRequest,
    MembershipWriteResponse,
    InvitationCreateRequest,
    InvitationTokenRequest,
    InvitationCompletionRequest,
    InvitationRegistrationResponse,
    InvitationDetailsResponse,
    InvitationListResponse,
)

_TUPLE_CONTRACT_MODEL: tuple[tuple[type[BaseModel], JsonSchemaMode], ...] = (
    (LoginRequest, "validation"),
    (CsrfResponse, "serialization"),
    (SessionResponse, "serialization"),
    (AccountAccessResponse, "serialization"),
    (DepartmentUpdateRequest, "validation"),
    (DepartmentCreationRequest, "validation"),
    (DepartmentDeletionRequest, "validation"),
    (DepartmentWriteResponse, "serialization"),
    (DepartmentListResponse, "serialization"),
    (DepartmentDetailsResponse, "serialization"),
    (DepartmentDeletionPreviewResponse, "serialization"),
    (DepartmentDeletionResponse, "serialization"),
    (MemberListResponse, "serialization"),
    (MemberDetailsResponse, "serialization"),
    (MembershipUpdateRequest, "validation"),
    (MembershipWriteResponse, "serialization"),
    (AccountDeletionRequest, "validation"),
    (AccountDeletionPreviewResponse, "serialization"),
    (InvitationCreateRequest, "validation"),
    (InvitationTokenRequest, "validation"),
    (InvitationCompletionRequest, "validation"),
    (InvitationRegistrationResponse, "serialization"),
    (InvitationDetailsResponse, "serialization"),
    (InvitationListResponse, "serialization"),
    (MessageResponse, "serialization"),
    (ExecutorListResponse, "serialization"),
    (ExecutorDetailsResponse, "serialization"),
    (ExecutorUpdateRequest, "validation"),
    (ExecutorCreationRequest, "validation"),
    (ExecutorDeletionRequest, "validation"),
    (ExecutorDispatchRequest, "validation"),
    (ExecutorUnassociateRequest, "validation"),
    (ExecutorUpdateResponse, "serialization"),
    (ExecutorGroupUpdateRequest, "validation"),
    (ExecutorGroupCreationRequest, "validation"),
    (ExecutorGroupDeletionRequest, "validation"),
    (ExecutorGroupListResponse, "serialization"),
    (ExecutorGroupDetailsResponse, "serialization"),
    (ExecutorGroupDeletionResponse, "serialization"),
    (ExecutorGroupWriteResponse, "serialization"),
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
        description="Generate browser API TypeScript types from backend contracts, or check them without changing the file."
    )
    argumentParser.add_argument("--check", action="store_true")
    argumentParser.add_argument(
        "--node",
        default="node",
        help="Node.js executable path (default: node from PATH).",
    )
    arguments = argumentParser.parse_args()
    boolCheck = bool(arguments.check)
    strNodePath: str = arguments.node
    pathOutput = _PATH_CONSOLE / "frontend/src/api/generated/browserApi.ts"
    # Keep the schema in memory and let the existing converter handle TypeScript syntax.
    try:
        completedProcess = subprocess.run(
            [
                strNodePath,
                str(_PATH_CONSOLE / "frontend/scripts/generateApiTypes.mjs"),
            ],
            cwd=_PATH_CONSOLE,
            input=json.dumps(build_browser_contract_schema(), sort_keys=True),
            stdout=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError:
        print(
            "Node.js was not found. Add it to PATH or pass --node with its executable path.",
            file=sys.stderr,
        )
        return 1
    if completedProcess.returncode != 0:
        return 1
    strExpected = completedProcess.stdout
    if boolCheck:
        if (
            not pathOutput.is_file()
            or pathOutput.read_text(encoding="utf-8") != strExpected
        ):
            print(
                "Browser API types are out of date. Run this command again without --check.",
                file=sys.stderr,
            )
            return 1
    else:
        pathOutput.parent.mkdir(parents=True, exist_ok=True)
        pathOutput.write_text(strExpected, encoding="utf-8", newline="\n")
    if boolCheck:
        print("Browser API TypeScript types match backend contracts.")
    else:
        print("Browser API TypeScript types generated from backend contracts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
