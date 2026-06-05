# -*- coding: utf-8 -*-
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # تمام روت‌های API پروژه از طریق فایل urls.py داخل ماژول core در دسترس خواهند بود
    path('api/', include('core.urls')),
]