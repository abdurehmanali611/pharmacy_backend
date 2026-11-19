from rest_framework.pagination import PageNumberPagination


class FlexiblePageNumberPagination(PageNumberPagination):
    """Honour ?page_size=N (the frontend sends it) instead of silently ignoring it."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 1000
