from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from core.audit import audit
from core.demo import deny_demo
from core.views import PolicyAPIView


class OrgListView(PolicyAPIView):
    """Small reference lists: returned whole, no pagination."""

    policy_actions = {"GET": "org.read", "POST": "org.manage"}
    model = None
    serializer_class = None
    search_fields: tuple[str, ...] = ("name",)

    def get(self, request):
        qs = self.model.objects.all()
        q = request.query_params.get("q", "").strip()
        if q:
            cond = Q()
            for field in self.search_fields:
                cond |= Q(**{f"{field}__icontains": q})
            qs = qs.filter(cond)
        return Response(self.serializer_class(qs, many=True).data)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        audit(request, "org.create", target=obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OrgDetailView(PolicyAPIView):
    policy_actions = {"PATCH": "org.manage", "DELETE": "org.manage"}
    model = None
    serializer_class = None

    def patch(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        serializer = self.serializer_class(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit(request, "org.update", target=obj)
        return Response(serializer.data)

    def delete(self, request, pk):
        deny_demo(request.user, "delete organisation data")
        obj = get_object_or_404(self.model, pk=pk)
        try:
            obj.delete()
        except ProtectedError:
            return Response(
                {"detail": "This entry is used by jobs and cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        audit(request, "org.delete", target=None, model=self.model._meta.model_name, id=str(pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
