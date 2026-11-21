from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Fail at start-up (not on first request) if the policy file is broken.
        from .policy import load_policy

        load_policy()
