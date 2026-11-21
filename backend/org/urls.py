from django.urls import path

from .models import Department, JobLevel, Location, Skill
from .serializers import DepartmentSerializer, JobLevelSerializer, LocationSerializer, SkillSerializer
from .views import OrgDetailView, OrgListView

RESOURCES = [
    ("departments", Department, DepartmentSerializer, ("name",)),
    ("locations", Location, LocationSerializer, ("name", "country")),
    ("job-levels", JobLevel, JobLevelSerializer, ("name",)),
    ("skills", Skill, SkillSerializer, ("name", "category")),
]

urlpatterns = []
for prefix, model, serializer, search in RESOURCES:
    urlpatterns += [
        path(
            prefix,
            OrgListView.as_view(model=model, serializer_class=serializer, search_fields=search),
            name=f"{prefix}-list",
        ),
        path(
            f"{prefix}/<uuid:pk>",
            OrgDetailView.as_view(model=model, serializer_class=serializer),
            name=f"{prefix}-detail",
        ),
    ]
