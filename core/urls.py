# -*- coding: utf-8 -*-
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.views import (
    AuthTokenView, UserViewSet, SellerViewSet, CustomerViewSet,
    SaleViewSet, ExpenseViewSet, DamageReportViewSet,
    ItemExitViewSet, ChecklistViewSet, TaskViewSet, DepositOrderViewSet,
    BranchListView, MissionViewSet, RoleViewSet, ChecklistLogViewSet, ClaimViewSet,
    DamageRegistrationViewSet, ReturnRequestViewSet, ReportDefinitionViewSet, ReportSubmissionViewSet,
    BranchTransferViewSet, WasteReportViewSet, AdvanceRequestViewSet, FileUploadView,
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
router.register(r'missions', MissionViewSet, basename='mission')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'checklist-logs', ChecklistLogViewSet, basename='checklist-logs')
router.register(r'claims', ClaimViewSet, basename='claim')
router.register(r'damage-registrations', DamageRegistrationViewSet, basename='damage-registration')
router.register(r'return-requests', ReturnRequestViewSet, basename='return-request')
router.register(r'report-definitions', ReportDefinitionViewSet, basename='report-definition')
router.register(r'report-submissions', ReportSubmissionViewSet, basename='report-submission')
router.register(r'transfers',          BranchTransferViewSet,    basename='branch-transfer')
router.register(r'waste-reports',      WasteReportViewSet,       basename='waste-report')
router.register(r'advance-requests', AdvanceRequestViewSet, basename='advance-request')

urlpatterns = [
    path('auth/token/', AuthTokenView.as_view(), name='auth_token_login'),
    path('branches/', BranchListView.as_view(), name='branch_list'),
    path('upload/', FileUploadView.as_view(), name='file_upload'),
    path('upload-image/', FileUploadView.as_view(), name='image_upload'),
    path('', include(router.urls)),
]