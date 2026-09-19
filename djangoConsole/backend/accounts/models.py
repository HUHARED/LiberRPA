# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower, Trim
from django.utils import timezone

from .passwords import validate_new_password


class UserManager(BaseUserManager["User"]):
    @classmethod
    def normalize_email(cls, email: str) -> str:
        # Reuse Django's Unicode normalization; email casing is not significant here.
        return AbstractBaseUser.normalize_username(email).strip().lower()

    def get_by_natural_key(self, username: str) -> "User":
        # Django calls the login identifier "username", even for email login.
        return self.get(email=self.normalize_email(username))

    async def aget_by_natural_key(self, username: str) -> "User":
        return await self.aget(email=self.normalize_email(username))

    def create_user(
        self, email: str, password: str | None = None, *, username: str
    ) -> "User":
        """Create an account record; callers handle verified registration and membership."""
        user = self.model(email=self.normalize_email(email), username=username.strip())
        # Validate fields once. The database enforces uniqueness at the actual write.
        user.full_clean(
            exclude=["password"], validate_unique=False, validate_constraints=False
        )
        if password is not None:
            validate_new_password(password, user)
        # None deliberately creates an unusable password, following Django's API.
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    """Account identity; organization and department permissions are separate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150)
    # Reserved for platform suspension, not an ordinary member-management switch.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(email=Lower(Trim("email"))) & ~models.Q(email=""),
                name="accounts_user_email_canonical",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.username} ({self.email})"
