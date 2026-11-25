import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models

from core.fields import EncryptedTextField


class Role(models.TextChoices):
    CANDIDATE = "candidate", "Candidate"
    RECRUITER = "recruiter", "Recruiter"
    MANAGER = "manager", "Manager"
    EMPLOYEE = "employee", "Employee"
    HR = "hr", "HR"
    ADMIN = "admin", "Admin"


# Roles an admin can give (D-80): never candidate (people register) and never admin
# (created only with the bootstrap_admin command).
STAFF_ROLES = (Role.RECRUITER, Role.MANAGER, Role.EMPLOYEE, Role.HR)


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
    # Prompt 1 (D-81, D-82). Date of birth is a locked field: set once by the person, then only
    # an admin can change it (audited, with a reason). Stored encrypted as YYYY-MM-DD.
    date_of_birth = EncryptedTextField(blank=True, default="")
    # Profile photo (compressed and encrypted like every file). Never shown to the fit scorer
    # or on application screens.
    photo = models.ForeignKey(
        "files.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    linkedin_url = models.CharField(max_length=200, blank=True, default="")
    github_url = models.CharField(max_length=200, blank=True, default="")
    portfolio_url = models.CharField(max_length=200, blank=True, default="")
    # Skill names the person lists (pre-filled from the resume at registration).
    skills = models.JSONField(default=list, blank=True)
    # JSON lists, encrypted: [{"qualification", "college", "branch", "year", "score"}] and
    # [{"company", "title", "start", "end", "responsibilities"}].
    education = EncryptedTextField(blank=True, default="")
    experience = EncryptedTextField(blank=True, default="")
    # {"applications": true, "interviews": true, ...}; missing keys mean "on".
    notification_prefs = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile of {self.user_id}"
