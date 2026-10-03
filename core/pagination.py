# -*- coding: utf-8 -*-
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class OptionalPageNumberPagination(PageNumberPagination):
    """
    صفحه‌بندی هوشمند دوحالته (Backward-Compatible):
    1. اگر کلاینت پارامتر 'page' یا 'page_size' را ارسال نکند (مانند نسخه‌های قدیمی اپلیکیشن)،
       صفحه‌بندی فعال نشده و داده‌ها به همان صورت آرایه خام قبلی برگردانده می‌شوند.
    2. اگر کلاینت پارامتر 'page' یا 'page_size' را بفرستد (مانند نسخه‌های جدید با اینفینیت اسکرول)،
       خروجی ساختار استاندارد صفحه‌بندی شامل count, total_pages, current_page, results و ... خواهد بود.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        if 'page' not in request.query_params and 'page_size' not in request.query_params:
            return None
        return super().paginate_queryset(queryset, request, view=view)

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
