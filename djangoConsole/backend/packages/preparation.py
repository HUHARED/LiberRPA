# FileName: preparation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.exceptions import ValidationError
from django.db.models import Q, F
from django.utils import timezone

from accounts.resource_authentication import NativeResourceAuthenticationContext
from operations.audit import record_audit
from executors.models import Executor, ExecutorSession, ExecutorGroupMember
from organizations.permissions import OrganizationAccessContext
from runs.control_notifications import notify_executor_control

from .models import Package, PackagePreparation, PackagePreparationState
from .queries import require_package_department


def request_package_preparation(package: Package, executorIds: list[uuid.UUID]) -> None:
    """Persist optional preparation independently of Schedule enablement and asset input values."""
    for executor in Executor.objects.filter(
        pk__in=executorIds,
        department_id=package.department_id,
        deleted_at__isnull=True,
    ):
        preparation, boolCreated = PackagePreparation.objects.get_or_create(
            package=package,
            executor=executor,
            python_environment_name=package.python_environment_name,
        )
        boolRetry = preparation.state == PackagePreparationState.FAILED
        if boolRetry:
            preparation.state = PackagePreparationState.PENDING
            preparation.reason = ""
            preparation.updated_at = timezone.now()
            preparation.save(update_fields=["state", "reason", "updated_at"])
        if boolCreated or boolRetry:
            notify_executor_control(executor.id)


def request_referenced_preparation(package: Package) -> None:
    from schedules.models import Schedule

    schedules = Schedule.objects.filter(package=package, deleted_at__isnull=True)
    setExecutorId = {
        uuid.UUID(strExecutorId)
        for schedule in schedules
        for strExecutorId in schedule.executor_ids
    }
    setExecutorId.update(
        ExecutorGroupMember.objects.filter(
            group_id__in=schedules.exclude(group_id=None).values("group_id")
        ).values_list("executor_id", flat=True)
    )
    request_package_preparation(package, list(setExecutorId))


def get_preparation_commands(
    access: OrganizationAccessContext, session: ExecutorSession
) -> list[dict]:
    if session.executor_id is None:
        return []
    executor = Executor.objects.get(pk=session.executor_id, deleted_at__isnull=True)
    require_package_department(access, executor.department_id)
    listCommand = []
    preparations = (
        PackagePreparation.objects
        .filter(
            executor=executor,
            package__department_id=executor.department_id,
            python_environment_name=F("package__python_environment_name"),
        )
        .filter(
            Q(
                state__in=[
                    PackagePreparationState.PENDING,
                    PackagePreparationState.PREPARING,
                ]
            )
            | ~Q(session_id=session.pk)
        )
        .select_related("package__blob")
        .order_by("updated_at")[:10]
    )
    for preparation in preparations:
        package = preparation.package
        preparation.session_id = session.pk
        preparation.state = PackagePreparationState.PREPARING
        preparation.reason = ""
        preparation.updated_at = timezone.now()
        preparation.save(update_fields=["session_id", "state", "reason", "updated_at"])
        listCommand.append({
            "preparation_id": str(preparation.pk),
            "inputs": {
                "package_id": str(package.pk),
                "sha256": package.sha256,
                "python_environment_name": preparation.python_environment_name,
                "requires_liberrpa": package.requires_liberrpa,
                "project_name": package.project_name,
                "project_version": package.version,
            },
        })
    return listCommand


def cancel_package_preparation(
    access: OrganizationAccessContext, package: Package
) -> int:
    require_package_department(access, package.department_id, manage=True)
    preparations = PackagePreparation.objects.filter(
        package=package,
        state__in=[PackagePreparationState.PENDING, PackagePreparationState.PREPARING],
    )
    setExecutorId = set(preparations.values_list("executor_id", flat=True))
    intCanceledCount, _ = preparations.delete()
    if intCanceledCount:
        record_audit(
            "packages.cancel_preparation",
            actor=access.actor,
            organization=access.organization,
            target=package,
            channel=access.channel,
            metadata={"canceled_count": intCanceledCount},
        )
        for executorId in setExecutorId:
            notify_executor_control(executorId)
    return intCanceledCount


def complete_preparation(
    access: OrganizationAccessContext,
    authentication: NativeResourceAuthenticationContext,
    preparationId: uuid.UUID,
    state: str,
    reason: str,
) -> None:
    session = ExecutorSession.objects.get(pk=authentication.sessionId)
    preparation = (
        PackagePreparation.objects
        .select_related("package")
        .filter(
            pk=preparationId,
            package__department__organization=access.organization,
        )
        .first()
    )
    # Canceled requests are removed; a later request has a new ID and cannot use this report.
    if preparation is None:
        return
    if (
        preparation.executor_id != session.executor_id
        or preparation.session_id != session.pk
    ):
        raise PackagePreparation.DoesNotExist(
            "This preparation belongs to another session."
        )
    require_package_department(access, preparation.package.department_id)
    if preparation.python_environment_name != preparation.package.python_environment_name:
        raise ValidationError(
            "The Package environment changed; prepare the current configuration."
        )
    if preparation.state in (
        PackagePreparationState.READY,
        PackagePreparationState.FAILED,
    ):
        if preparation.state != state:
            raise ValidationError("This preparation already has a different result.")
        return
    preparation.state = state
    preparation.reason = reason if state == PackagePreparationState.FAILED else ""
    preparation.updated_at = timezone.now()
    preparation.save(update_fields=["state", "reason", "updated_at"])
    # Completing this batch allows the Executor to receive further preparation commands.
    notify_executor_control(preparation.executor_id)


def get_package_preparation(package: Package) -> list[dict]:
    return [
        {
            "executor_id": str(preparation.executor_id),
            "executor_name": preparation.executor.name,
            "python_environment_name": preparation.python_environment_name,
            "state": preparation.state,
            "reason": preparation.reason,
            "updated_at": preparation.updated_at.isoformat(),
        }
        for preparation in PackagePreparation.objects
        .filter(
            package=package,
            python_environment_name=package.python_environment_name,
            executor__deleted_at__isnull=True,
        )
        .select_related("executor")
        .order_by("executor__name", "executor_id")
    ]


def record_package_preparation(
    packageId: uuid.UUID,
    executorId: uuid.UUID,
    sessionId: uuid.UUID,
    environmentName: str,
    state: str,
    reason: str = "",
) -> None:
    if state not in (PackagePreparationState.READY, PackagePreparationState.FAILED):
        raise ValueError("A completed preparation must be ready or failed.")
    package = Package.objects.filter(pk=packageId).first()
    if package is None:
        return
    PackagePreparation.objects.update_or_create(
        package=package,
        executor_id=executorId,
        python_environment_name=environmentName,
        defaults={
            "session_id": sessionId,
            "state": state,
            "reason": reason[:2000],
            "updated_at": timezone.now(),
        },
    )
