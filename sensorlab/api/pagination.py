"""One page size for the whole app, so SL-B2's resources do not each invent
their own and the schema can state it as a fact rather than a guess."""

from rest_framework.pagination import PageNumberPagination


class SensorLabPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
