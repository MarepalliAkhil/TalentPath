from django.apps import AppConfig


class HrConfig(AppConfig):
    name = "hr"
    verbose_name = "People operations"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401  (connects the offer_accepted receiver)
