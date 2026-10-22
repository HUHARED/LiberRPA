# FileName: rate_limits.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Callable
from enum import StrEnum
from typing import cast

from django.http import HttpRequest
from django.utils.crypto import salted_hmac

from console_project.rate_limits import apply_request_rate_limit

from .models import Organization
from .limits import get_organization_limits

_STR_POLICY_ATTRIBUTE = "_console_request_budget"
_STR_CHECKED_ATTRIBUTE = "_console_budget_checked"


class RequestBudget(StrEnum):
    READ = "read"
    WRITE = "write"
    CONTROL = "control"
    INDEPENDENT = "independent"
    DEFERRED = "deferred"


class RequestBudgetError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status: int,
        retryAfterSeconds: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryAfterSeconds = retryAfterSeconds


def request_budget[View: Callable](
    budget: RequestBudget, *, methods: tuple[str, ...] | None = None
) -> Callable[[View], View]:
    """Declare an endpoint exception to method-based accounting, without wrapping it."""

    def decorate(view: View) -> View:
        setattr(view, _STR_POLICY_ATTRIBUTE, (budget, methods))
        return view

    return decorate


def get_request_budget(request: HttpRequest) -> RequestBudget:
    # Run-file streaming uses a synthetic request after download admission.
    if request.resolver_match is None:
        return RequestBudget.INDEPENDENT
    policy = cast(
        tuple[RequestBudget, tuple[str, ...] | None] | None,
        getattr(request.resolver_match.func, _STR_POLICY_ATTRIBUTE, None),
    )
    if policy is not None:
        budget, methods = policy
        if methods is None or request.method in methods:
            return budget
    return (
        RequestBudget.READ
        if request.method in ("GET", "HEAD", "OPTIONS")
        else RequestBudget.WRITE
    )


def get_request_budget_key(organizationId: uuid.UUID, budget: RequestBudget) -> str:
    return salted_hmac(
        f"organizations.requests.{budget.value}", str(organizationId), algorithm="sha256"
    ).hexdigest()


def check_request_budget(
    request: HttpRequest,
    organization: Organization,
    *,
    budget: RequestBudget | None = None,
    cost: int = 1,
) -> None:
    """Charge verified HTTP identity once, before any business transaction.

    Deferred endpoints supply their validated batch size.
    Account/security flows, execution control and already accepted transfers retain independent safeguards.
    """
    if getattr(request, _STR_CHECKED_ATTRIBUTE, False):
        return
    if budget is None:
        budget = get_request_budget(request)
    if budget in (
        RequestBudget.CONTROL,
        RequestBudget.INDEPENDENT,
        RequestBudget.DEFERRED,
    ):
        return

    limits = get_organization_limits(organization)
    intLimit = (
        limits.organizationReadRequestsPerMinute
        if budget == RequestBudget.READ
        else limits.organizationWriteObjectsPerMinute
    )
    if intLimit == 0:
        raise RequestBudgetError(
            f"{budget.value.capitalize()} requests are disabled for this organization.",
            code="organization_requests_disabled",
            status=403,
        )
    if cost > intLimit:
        raise RequestBudgetError(
            f"This request exceeds the organization's allowance of {intLimit} object operations per minute. "
            "Select fewer items.",
            code="organization_request_too_large",
            status=400,
        )

    intRetryAfter = apply_request_rate_limit(
        get_request_budget_key(organization.pk, budget),
        maxRequests=intLimit,
        windowSeconds=60,
        cost=cost,
    )
    if intRetryAfter:
        raise RequestBudgetError(
            f"The organization's {budget.value} request limit has been reached. "
            f"Try again in {intRetryAfter} seconds.",
            code=f"organization_{budget.value}_rate_limited",
            status=429,
            retryAfterSeconds=intRetryAfter,
        )
    setattr(request, _STR_CHECKED_ATTRIBUTE, True)
