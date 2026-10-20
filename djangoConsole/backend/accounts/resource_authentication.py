# FileName: resource_authentication.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
from typing import cast

from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.debug import sensitive_variables

from console_project.http import build_error_response, build_rate_limited_response
from executors.client_sessions import (
    InvalidExecutorSessionError,
    ExecutorClientAction,
    ExecutorClientResult,
    get_executor_session_identity,
    get_locked_executor_session,
    open_executor_client_request,
)
from organizations.rate_limits import (
    RequestBudget,
    check_request_budget,
    get_request_budget,
)
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    resolve_organization_access,
)

from .api_key_authentication import (
    InvalidApiKeyError,
    ApiKeyAuthenticationContext,
    authenticate_api_key,
    lock_api_key_write_access,
)
from .editor_sessions import (
    InvalidEditorSessionError,
    EditorClientAction,
    EditorClientResult,
    get_locked_editor_session,
    handle_editor_client_request,
)
from .rate_limits import (
    apply_api_key_authentication_rate_limit,
    apply_native_resource_authentication_rate_limit,
)


class InvalidResourceCredentialError(Exception):
    """The original native login no longer authorizes resource access."""


@dataclass(frozen=True)
class NativeResourceAuthenticationContext:
    sessionId: uuid.UUID
    access: OrganizationAccessContext

    @property
    def apiKeyId(self) -> None:
        return None


type ResourceAuthenticationContext = (
    ApiKeyAuthenticationContext | NativeResourceAuthenticationContext
)


@sensitive_variables()
def _get_credential_channel(authorizationHeader: str) -> AccessChannel:
    # This selects a parser and rate counter, not an authenticated identity.
    listHeaderPart = authorizationHeader.split(" ", 1)
    if len(listHeaderPart) == 2 and listHeaderPart[0].lower() == "bearer":
        strCredential = listHeaderPart[1].lstrip(" ")
        if strCredential.startswith("lred_"):
            return AccessChannel.EDITOR
        if strCredential.startswith("lrex_"):
            return AccessChannel.EXECUTOR
    return AccessChannel.API_KEY


@sensitive_variables()
def authenticate_resource(authorizationHeader: str) -> ResourceAuthenticationContext:
    """Authenticate each request using the existing key or native-session rules.

    Native contact renews only its original session. Cookies and a supplied Run ID never establish this identity.
    Call before entering a business transaction.
    """
    accessChannel = _get_credential_channel(authorizationHeader)
    if accessChannel == AccessChannel.API_KEY:
        return authenticate_api_key(authorizationHeader)
    try:
        clientResult: EditorClientResult | ExecutorClientResult
        if accessChannel == AccessChannel.EDITOR:
            clientResult = cast(
                EditorClientResult,
                handle_editor_client_request(
                    authorizationHeader=authorizationHeader,
                    action=EditorClientAction.SESSION,
                ),
            )
        else:
            with open_executor_client_request(
                identity=get_executor_session_identity(authorizationHeader),
                action=ExecutorClientAction.RESOURCE,
            ) as executorResult:
                clientResult = cast(ExecutorClientResult, executorResult)
    except (InvalidEditorSessionError, InvalidExecutorSessionError):
        raise InvalidResourceCredentialError(
            "Sign in again to use Console resources."
        ) from None
    except ValidationError as e:
        if getattr(e, "code", None) != "executor_selection_required":
            raise
        raise InvalidResourceCredentialError(
            "Select an Executor to finish signing in before using Console resources."
        ) from None
    return NativeResourceAuthenticationContext(
        sessionId=clientResult.session.pk, access=clientResult.access
    )


def lock_resource_write_access(
    authentication: ResourceAuthenticationContext,
) -> OrganizationAccessContext:
    """Recheck current credentials after waiting for the transaction's write locks."""
    if isinstance(authentication, ApiKeyAuthenticationContext):
        return lock_api_key_write_access(authentication)
    access = resolve_organization_access(
        actorId=authentication.access.actorId,
        organizationId=authentication.access.organization.pk,
        channel=authentication.access.channel,
        forUpdate=True,
    )
    try:
        if access.channel == AccessChannel.EDITOR:
            get_locked_editor_session(access, authentication.sessionId)
        elif access.channel == AccessChannel.EXECUTOR:
            session = get_locked_executor_session(access, authentication.sessionId)
            if session.executor_id is None:
                raise InvalidExecutorSessionError("An associated Executor is required.")
        else:
            raise InvalidResourceCredentialError("Unsupported native access channel.")
    except (InvalidEditorSessionError, InvalidExecutorSessionError):
        raise InvalidResourceCredentialError(
            "Sign in again to use Console resources."
        ) from None
    return access


def build_resource_authentication_required_response() -> JsonResponse:
    response = build_error_response(
        "authentication_required", "Valid credentials are required.", statusCode=401
    )
    response["WWW-Authenticate"] = (
        'Bearer realm="LiberRPA Console", error="invalid_token"'
    )
    return response


@sensitive_variables()
def authenticate_resource_request(
    request: HttpRequest,
) -> ResourceAuthenticationContext | JsonResponse:
    strAuthorization = request.headers.get("Authorization", "")
    strClientAddress = request.META.get("REMOTE_ADDR", "")
    if _get_credential_channel(strAuthorization) == AccessChannel.API_KEY:
        intRetryAfter = apply_api_key_authentication_rate_limit(
            strClientAddress,
            control=get_request_budget(request) == RequestBudget.CONTROL,
        )
    else:
        intRetryAfter = apply_native_resource_authentication_rate_limit(strClientAddress)
    if intRetryAfter:
        return build_rate_limited_response(intRetryAfter)
    try:
        authentication = authenticate_resource(strAuthorization)
    except (InvalidApiKeyError, InvalidResourceCredentialError):
        return build_resource_authentication_required_response()
    check_request_budget(request, authentication.access.organization)
    return authentication
