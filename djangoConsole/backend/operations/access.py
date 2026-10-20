# FileName: access.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from accounts.session_revocation import require_current_session


@sensitive_variables()
def get_platform_actor(request: HttpRequest, *, forUpdate: bool = False) -> User:
    """Resolve platform permission independently of organization membership.

    Writes require the caller's transaction and any target organization lock first.
    """
    if not request.user.is_authenticated:
        raise PermissionDenied("Sign in to continue.")

    userQuery = User.objects.all()
    if forUpdate:
        userQuery = userQuery.select_for_update()
    try:
        actor = userQuery.get(pk=request.user.pk)
    except User.DoesNotExist:
        raise PermissionDenied("Platform administrator access is required.") from None

    if forUpdate:
        require_current_session(
            actor,
            request.session.get(HASH_SESSION_KEY, ""),
            request.session.get_expiry_date(),
            request.session.session_key,
        )
    if not actor.is_active or not actor.is_platform_admin:
        raise PermissionDenied("Platform administrator access is required.")
    return actor
