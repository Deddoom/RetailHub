# -*- coding: utf-8 -*-
"""
WSGI config for my_retail_project.
It exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
from django.core.wsgi import get_wsgi_application

# تنظیم ماژول تنظیمات پیش‌فرض برای اجرای پروژه
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

application = get_wsgi_application()