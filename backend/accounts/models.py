import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from core.fields import EncryptedTextField


class Role(models.TextChoices):
    CANDIDATE = "candidate", "Candidate"
    RECRUITER = "recruiter", "Recruiter"
    HIRING_MANAGER = "hiring_manager", "Hiring manager"
    EMPLOYEE = "employee", "Employee"
    HR_ADMIN = "hr_admin", "HR admin"


STAFF_ROLES = (Role.RECRUITER, Role.HIRING_MANAGER, Role.EMPLOYEE, Role.HR_ADMIN)


class UserManager(BaseUserManager):
    def get_by_natural_key(self, username):
        return self.get(email__iexact=(username or "").strip())

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    full_name = models.CharField(max_length=120)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CANDIDATE, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.role})"


class Profile(models.Model):
    """Personal data. Phone and address are encrypted at rest."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    headline = models.CharField(max_length=160, blank=True, default="")
    location_text = models.CharField(max_length=120, blank=True, default="")
    phone = EncryptedTextField(blank=True, default="")
    phone_bidx = models.CharField(max_length=64, blank=True, default="", db_index=True)
    address = EncryptedTextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile of {self.user_id}"
