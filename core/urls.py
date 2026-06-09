# -*- coding: utf-8 -*-
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (
    AuthTokenView, UserViewSet, SellerViewSet, CustomerViewSet,
    SaleViewSet, ExpenseViewSet, DamageReportViewSet,
    ItemExitViewSet, ChecklistViewSet, TaskViewSet, DepositOrderViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'sellers', SellerViewSet, basename='seller')
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'sales', SaleViewSet, basename='sale')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'damage-reports', DamageReportViewSet, basename='damage-report')
router.register(r'item-exits', ItemExitViewSet, basename='item-exit')
router.register(r'checklists', ChecklistViewSet, basename='checklist')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'deposit-orders', DepositOrderViewSet, basename='deposit-order')

urlpatterns = [
    path('auth/token/', AuthTokenView.as_view(), name='auth_token_login'),
    path('', include(router.urls)),
]