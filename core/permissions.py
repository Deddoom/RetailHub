# -*- coding: utf-8 -*-
from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'ADMIN'

class IsOwnerOrAdminOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'ADMIN':
            return True
        if request.user.role == 'CASHIER':
            if request.method in permissions.SAFE_METHODS:
                return True
            return getattr(obj, 'created_by', None) == request.user
        return False
    

class IsSuperiorUser(permissions.BasePermission):
    """
    مجوز دسترسی برای مأموریت‌ها و چک‌لیست‌ها.
    فقط بالادستی‌ها می‌توانند ایجاد، ویرایش یا حذف کنند.
    کاربران عادی فقط می‌توانند وظایف خود را مشاهده کنند.
    """
    def has_permission(self, request, view):
        # کاربر حتما باید احراز هویت شده باشد
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # برای عملیات خواندن (GET) روی یک مأموریت یا چک‌لیست خاص:
        # یا خودش صاحب آن است، یا سازنده‌اش است، یا بالادستِ شخصِ تخصیص‌یافته است.
        if request.method in permissions.SAFE_METHODS:
            return (
                obj.assigned_to == request.user or 
                obj.created_by == request.user or 
                request.user.is_superior_to(obj.assigned_to)
            )
        
        # برای عملیات‌های تغییر و حذف (PUT, PATCH, DELETE):
        # سازنده‌ی اصلی یا هرکسی که بالادستِ شخصِ تخصیص‌یافته است دسترسی دارد.
        return obj.created_by == request.user or request.user.is_superior_to(obj.assigned_to)