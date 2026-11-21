from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


def paginate(view, request, queryset, serialize):
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    return paginator.get_paginated_response([serialize(obj) for obj in page])


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """For sitemap/robots: crawlers send all kinds of Accept headers."""

    def select_parser(self, request, parsers):
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type
