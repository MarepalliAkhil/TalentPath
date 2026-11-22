from django.urls import path

from . import views

urlpatterns = [path("fairness/check", views.FairnessCheckView.as_view(), name="fairness-check")]
