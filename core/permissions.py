# -*- coding: utf-8 -*-
from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_superuser or any(
            r.code == 'ADMIN' for r in request.user.roles.all()
        )

class IsOwnerOrAdminOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def _is_admin(self, user):
        return user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())

    def _is_cashier(self, user):
        return any(r.code == 'CASHIER' for r in user.roles.all())

    def has_object_permission(self, request, view, obj):
        if self._is_admin(request.user):
            return True
        if self._is_cashier(request.user):
            if request.method in permissions.SAFE_METHODS:
                return True
            return getattr(obj, 'created_by', None) == request.user
        return False

class IsSuperiorUser(permissions.BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
            
        # بررسی منطق ارجاع در هنگام ساخت رکورد جدید (POST)
        if request.method == 'POST' and 'assigned_to' in request.data:
            if request.user.is_superuser or any(r.code == 'ADMIN' for r in request.user.roles.all()):
                return True
                
            assigned_to_id = request.data.get('assigned_to')
            from core.models import CustomUser
            try:
                assigned_user = CustomUser.objects.get(id=assigned_to_id)
                # اجازه ساخت فقط در صورتی داده می‌شود که کاربر هدف، خود فرد یا زیردست او باشد
                if request.user == assigned_user or request.user.is_superior_to(assigned_user):
                    return True
                return False
            except CustomUser.DoesNotExist:
                # اجازه عبور می‌دهیم تا سریالایزر خطای 400 دقیق (کاربر یافت نشد) را پرتاب کند
                return True 
                
        return True

    def has_object_permission(self, request, view, obj):
        # ادمین دسترسی کامل دارد
        if request.user.is_superuser or any(r.code == 'ADMIN' for r in request.user.roles.all()):
            return True
            
        # در همه حالتها (حتی ویرایش)، خود فرد ارجاع‌شده، سازنده، یا بالادستی دسترسی دارند.
        return (
            obj.assigned_to == request.user or
            obj.created_by == request.user or
            request.user.is_superior_to(obj.assigned_to)
        )