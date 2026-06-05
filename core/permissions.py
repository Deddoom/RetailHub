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