# -*- coding: utf-8 -*-
import datetime
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.utils import timezone
from decimal import Decimal
from datetime import date
from rest_framework.permissions import IsAuthenticated

from core.models import (
    CustomUser, Seller, Customer,
    Sale, Payment, Expense,
    DamageReport, ItemExit,
    Checklist, Task,
    DepositOrder, DepositOrderItem,
    BRANCH_CHOICES, Mission, Role,
)
from core.serializers import (
    UserSerializer,
    SellerSerializer, SellerLookupSerializer,
    CustomerSerializer,
    SaleSerializer, SaleListSerializer,
    ExpenseSerializer,
    DamageReportSerializer, ItemExitSerializer,
    ChecklistSerializer, TaskSerializer,
    DepositOrderSerializer, DepositOrderListSerializer,
    MissionSerializer, RoleSerializer,
)
from core.authentication import StatelessTokenService
from core.permissions import IsAdminUser, IsOwnerOrAdminOnly, IsSuperiorUser


# ── Safe Destroy Mixin ────────────────────────────────────────────────────────

class SafeDestroyMixin:
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"error": "این رکورد دارای اطلاعات وابسته است و قابل حذف نمی‌باشد."},
                status=status.HTTP_400_BAD_REQUEST
            )


# ── Auth ──────────────────────────────────────────────────────────────────────

class AuthTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {"error": "نام کاربری و رمز عبور الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            return Response({"error": "مشخصات نامعتبر است."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({"error": "مشخصات نامعتبر است."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"error": "حساب کاربری غیرفعال است."}, status=status.HTTP_403_FORBIDDEN)

        access_token = StatelessTokenService.generate_token(user)
        roles = list(user.roles.values_list('code', flat=True))
        return Response(
            {"access_token": access_token, "roles": roles, "branch": user.branch},
            status=status.HTTP_200_OK
        )


# ── Branches ──────────────────────────────────────────────────────────────────

class BranchListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        branches = [{"value": v, "label": l} for v, l in BRANCH_CHOICES]
        return Response(branches, status=status.HTTP_200_OK)


# ── Users ─────────────────────────────────────────────────────────────────────

class UserViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = CustomUser.objects.all().order_by('-date_joined')
    serializer_class   = UserSerializer
    permission_classes = [IsAdminUser]


# ── Sellers ───────────────────────────────────────────────────────────────────

class SellerViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset         = Seller.objects.all()
    serializer_class = SellerSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'lookup']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='lookup')
    def lookup(self, request):
        sellers    = self.get_queryset()
        serializer = SellerLookupSerializer(sellers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ── Customers ─────────────────────────────────────────────────────────────────

class CustomerViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = Customer.objects.all()
    serializer_class   = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]


# ── Sales ─────────────────────────────────────────────────────────────────────

class SaleViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrAdminOnly]

    def get_serializer_class(self):
        return SaleListSerializer if self.action == 'list' else SaleSerializer

    def get_queryset(self):
        qs = Sale.objects.select_related(
            'seller', 'customer', 'created_by'
        ).prefetch_related('payments', 'payments__cheques', 'deposit_items')

        user = self.request.user
        if not (user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())):
            qs = qs.filter(created_by=user)

        for param, field in [
            ('branch',   'branch'),
            ('seller',   'seller__id'),
            ('customer', 'customer__id'),
        ]:
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{field: val})

        from_date = self.request.query_params.get('from_date')
        to_date   = self.request.query_params.get('to_date')
        if from_date:
            qs = qs.filter(date_time__date__gte=from_date)
        if to_date:
            qs = qs.filter(date_time__date__lte=to_date)

        return qs.order_by('-date_time')


# ── Expenses ──────────────────────────────────────────────────────────────────

class ExpenseViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    serializer_class   = ExpenseSerializer
    permission_classes = [IsOwnerOrAdminOnly]

    def get_queryset(self):
        qs       = Expense.objects.select_related('created_by').prefetch_related('cheques')
        user     = self.request.user
        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())
        return qs if is_admin else qs.filter(created_by=user)


# ── DamageReport ──────────────────────────────────────────────────────────────

class DamageReportViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = DamageReport.objects.all()
    serializer_class   = DamageReportSerializer
    permission_classes = [IsOwnerOrAdminOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── ItemExit ──────────────────────────────────────────────────────────────────

class ItemExitViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = ItemExit.objects.all()
    serializer_class   = ItemExitSerializer
    permission_classes = [IsOwnerOrAdminOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── DepositOrders ─────────────────────────────────────────────────────────────

class DepositOrderViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrAdminOnly]

    def get_serializer_class(self):
        return DepositOrderListSerializer if self.action == 'list' else DepositOrderSerializer

    def get_queryset(self):
        qs = DepositOrder.objects.select_related(
            'customer', 'seller', 'created_by', 'sale'
        ).prefetch_related('items')

        user = self.request.user
        if not (user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())):
            qs = qs.filter(created_by=user)

        branch       = self.request.query_params.get('branch')
        order_status = self.request.query_params.get('status')
        seller_id    = self.request.query_params.get('seller')
        customer_id  = self.request.query_params.get('customer')
        from_date    = self.request.query_params.get('from_date')
        to_date      = self.request.query_params.get('to_date')

        if branch:       qs = qs.filter(branch=branch)
        if order_status: qs = qs.filter(status=order_status)
        if seller_id:    qs = qs.filter(seller__id=seller_id)
        if customer_id:  qs = qs.filter(customer__id=customer_id)
        if from_date:    qs = qs.filter(created_at__date__gte=from_date)
        if to_date:      qs = qs.filter(created_at__date__lte=to_date)

        return qs.order_by('-created_at')

    @action(detail=True, methods=['patch'], url_path='settle')
    @transaction.atomic
    def settle(self, request, pk=None):
        order = self.get_object()

        if order.status == 'DELIVERED':
            return Response({"error": "این سفارش قبلاً تسویه شده است."}, status=status.HTTP_400_BAD_REQUEST)
        if order.status == 'CANCELLED':
            return Response({"error": "سفارش لغو شده قابل تسویه نیست."}, status=status.HTTP_400_BAD_REQUEST)

        debt_payment_method = request.data.get('debt_payment_method')
        if not debt_payment_method:
            return Response(
                {"error": "نحوه پرداخت بدهی (debt_payment_method) الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        net_amount = Decimal(str(order.total_amount)) - Decimal(str(order.discount_amount))

        sale = Sale.objects.create(
            branch=order.branch, seller=order.seller, customer=order.customer,
            created_by=request.user, total_amount=net_amount,
            remaining_balance=Decimal('0.00'),
            description=request.data.get('description', f"تسویه سفارش بیعانه {order.id}"),
        )

        if order.deposit_paid > 0:
            Payment.objects.create(
                sale=sale, payment_method=order.deposit_payment_method or 'OTHER',
                amount=order.deposit_paid, description="بیعانه پرداخت‌شده قبلی",
            )
        if order.remaining_debt > 0:
            Payment.objects.create(
                sale=sale, payment_method=debt_payment_method,
                amount=order.remaining_debt, description="پرداخت بدهی هنگام تحویل",
            )

        order.sale                = sale
        order.status              = 'DELIVERED'
        order.debt_payment_method = debt_payment_method
        order.deposit_paid        = net_amount
        order.save()

        customer = Customer.objects.select_for_update().get(pk=order.customer_id)
        customer.last_purchase_date    = date.today()
        customer.total_purchase_amount += net_amount
        customer.last_purchase_type    = debt_payment_method
        customer.save()

        return Response(
            {"message": "سفارش با موفقیت تسویه شد.", "sale_id": str(sale.id), "deposit_order_id": str(order.id)},
            status=status.HTTP_200_OK
        )


# ── Missions ──────────────────────────────────────────────────────────────────

class MissionViewSet(viewsets.ModelViewSet):
    serializer_class   = MissionSerializer
    permission_classes = [IsAuthenticated, IsSuperiorUser]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['title', 'description']

    def get_queryset(self):
        user = self.request.user
        user_roles = set(user.roles.values_list('code', flat=True))

        if user.is_superuser or 'ADMIN' in user_roles:
            return Mission.objects.all()

        all_users = CustomUser.objects.prefetch_related('roles').exclude(pk=user.pk)
        
        subordinate_ids = []
        for u in all_users:
            if user.is_superior_to(u):
                subordinate_ids.append(u.id)

        return Mission.objects.filter(
            Q(assigned_to=user) |
            Q(created_by=user)  |
            Q(assigned_to_id__in=subordinate_ids)
        ).distinct().order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        instance = self.get_object()
        user     = self.request.user
        data     = serializer.validated_data

        is_admin   = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())
        can_manage = is_admin or instance.created_by == user or user.is_superior_to(instance.assigned_to)
        is_owner   = instance.assigned_to == user

        if can_manage:
            serializer.save()
        elif is_owner:
            forbidden_fields = {k for k in data if k != 'status'}
            if forbidden_fields:
                raise PermissionDenied(
                    f"شما فقط مجاز به تغییر وضعیت انجام ماموریت (status) هستید. "
                    f"فیلدهای غیرمجاز: {', '.join(sorted(forbidden_fields))}"
                )
            serializer.save()
        else:
            raise PermissionDenied("شما دسترسی به ویرایش این ماموریت را ندارید.")


# ── Checklists ────────────────────────────────────────────────────────────────

class ChecklistViewSet(viewsets.ModelViewSet):
    serializer_class   = ChecklistSerializer
    permission_classes = [IsAuthenticated, IsSuperiorUser]

    def get_queryset(self):
        user = self.request.user
        user_roles = set(user.roles.values_list('code', flat=True))

        if user.is_superuser or 'ADMIN' in user_roles:
            return Checklist.objects.all()

        all_users = CustomUser.objects.prefetch_related('roles').exclude(pk=user.pk)
        
        subordinate_ids = []
        for u in all_users:
            if user.is_superior_to(u):
                subordinate_ids.append(u.id)

        return Checklist.objects.filter(
            Q(assigned_to=user) |
            Q(created_by=user)  |
            Q(assigned_to_id__in=subordinate_ids)
        ).distinct().order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class   = TaskSerializer
    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        return user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())

    def _can_manage_task(self, user, task):
        return (
            self._is_admin(user)
            or task.checklist.created_by == user
            or user.is_superior_to(task.checklist.assigned_to)
        )

    def get_queryset(self):
        user = self.request.user

        if self._is_admin(user):
            return Task.objects.select_related(
                'checklist', 'checklist__assigned_to', 'checklist__created_by'
            ).all()

        all_users = CustomUser.objects.prefetch_related('roles').exclude(pk=user.pk)
        subordinate_ids = [u.id for u in all_users if user.is_superior_to(u)]

        return Task.objects.filter(
            Q(checklist__assigned_to=user) |
            Q(checklist__created_by=user)  |
            Q(checklist__assigned_to_id__in=subordinate_ids)
        ).distinct()

    def perform_update(self, serializer):
        instance = self.get_object()
        user     = self.request.user
        data     = serializer.validated_data

        is_owner   = instance.checklist.assigned_to == user
        can_manage = self._can_manage_task(user, instance)

        def _save_with_completion():
            if 'is_completed' in data:
                if data['is_completed'] is True:
                    serializer.save(completed_by=user, completed_at=timezone.now())
                else:
                    serializer.save(completed_by=None, completed_at=None)
            else:
                serializer.save()

        if can_manage:
            _save_with_completion()
        elif is_owner:
            forbidden_fields = {k for k in data if k != 'is_completed'}
            if forbidden_fields:
                raise PermissionDenied(
                    f"شما فقط مجاز به تغییر وضعیت انجام تسک هستید. "
                    f"فیلدهای غیرمجاز: {', '.join(sorted(forbidden_fields))}"
                )
            _save_with_completion()
        else:
            raise PermissionDenied("شما دسترسی به ویرایش این تسک را ندارید.")


# ── Roles ─────────────────────────────────────────────────────────────────────

class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = Role.objects.all()
    serializer_class   = RoleSerializer
    permission_classes = [IsAdminUser]