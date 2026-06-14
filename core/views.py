# -*- coding: utf-8 -*-
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from decimal import Decimal
from datetime import date

from core.models import (
    CustomUser, Seller, Customer,
    Sale, Payment, Expense,
    DamageReport, ItemExit,
    Checklist, Task,
    DepositOrder, DepositOrderItem,
    BRANCH_CHOICES,
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
)
from core.authentication import StatelessTokenService
from core.permissions import IsAdminUser, IsOwnerOrAdminOnly


# ── Safe Destroy Mixin ────────────────────────────────────────────────────────

class SafeDestroyMixin:
    """
    جلوگیری از خطای ۵۰۰ هنگام حذف رکوردهایی که رکورد وابسته دارند.
    خطای ProtectedError را به یک پاسخ ۴۰۰ واضح تبدیل می‌کند.
    """
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
            return Response(
                {"error": "مشخصات نامعتبر است."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.check_password(password):
            return Response(
                {"error": "مشخصات نامعتبر است."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {"error": "حساب کاربری غیرفعال است."},
                status=status.HTTP_403_FORBIDDEN
            )

        access_token = StatelessTokenService.generate_token(user)
        return Response(
            {"access_token": access_token, "role": user.role, "branch": user.branch},
            status=status.HTTP_200_OK
        )


# ── شعب ───────────────────────────────────────────────────────────────────────

class BranchListView(APIView):
    """
    GET /api/branches/
    برمی‌گرداند لیست ثابت ۴ شعبه سیستم
    دسترسی: همه کاربران احراز هویت‌شده
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        branches = [{"value": v, "label": l} for v, l in BRANCH_CHOICES]
        return Response(branches, status=status.HTTP_200_OK)


# ── Users ─────────────────────────────────────────────────────────────────────

class UserViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset         = CustomUser.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
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
        """
        GET /api/sellers/lookup/
        لیست ساده برای پر کردن dropdown فرانت‌اند
        """
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
        if self.action == 'list':
            return SaleListSerializer
        return SaleSerializer

    def get_queryset(self):
        qs = Sale.objects.select_related(
            'seller', 'customer', 'created_by'
        ).prefetch_related(
            'payments', 'payments__cheques', 'deposit_items'
        )
        user = self.request.user
        if user.role != 'ADMIN':
            qs = qs.filter(created_by=user)

        branch      = self.request.query_params.get('branch')
        seller_id   = self.request.query_params.get('seller')
        customer_id = self.request.query_params.get('customer')
        from_date   = self.request.query_params.get('from_date')
        to_date     = self.request.query_params.get('to_date')

        if branch:
            qs = qs.filter(branch=branch)
        if seller_id:
            qs = qs.filter(seller__id=seller_id)
        if customer_id:
            qs = qs.filter(customer__id=customer_id)
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
        qs = Expense.objects.select_related('created_by').prefetch_related('cheques')
        return qs if self.request.user.role == 'ADMIN' else qs.filter(created_by=self.request.user)


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


# ── Checklists ────────────────────────────────────────────────────────────────

class ChecklistViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset         = Checklist.objects.all().prefetch_related('tasks')
    serializer_class = ChecklistSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUser()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TaskViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = Task.objects.all()
    serializer_class   = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user.role == 'USER':
            is_completed_val = request.data.get('is_completed', instance.is_completed)
            if isinstance(is_completed_val, str):
                is_completed_val = is_completed_val.lower() in ['true', '1', 'yes']

            instance.is_completed = bool(is_completed_val)
            instance.description  = request.data.get('description', instance.description)

            if instance.is_completed:
                instance.completed_by = request.user
                instance.completed_at = timezone.now()
            else:
                instance.completed_by = None
                instance.completed_at = None

            instance.save()
            return Response(self.get_serializer(instance).data)
        return super().update(request, *args, **kwargs)


# ── DepositOrders ─────────────────────────────────────────────────────────────

class DepositOrderViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    """
    CRUD کامل سفارش‌های بیعانه

    GET    /api/deposit-orders/                → لیست
    POST   /api/deposit-orders/                → ثبت سفارش جدید
    GET    /api/deposit-orders/{uuid}/         → جزئیات کامل + اقلام
    PUT    /api/deposit-orders/{uuid}/         → ویرایش کامل
    PATCH  /api/deposit-orders/{uuid}/         → ویرایش جزئی
    DELETE /api/deposit-orders/{uuid}/         → حذف
    PATCH  /api/deposit-orders/{uuid}/settle/  → تسویه نهایی
    """
    permission_classes = [IsOwnerOrAdminOnly]

    def get_serializer_class(self):
        if self.action == 'list':
            return DepositOrderListSerializer
        return DepositOrderSerializer

    def get_queryset(self):
        qs = DepositOrder.objects.select_related(
            'customer', 'seller', 'created_by', 'sale'
        ).prefetch_related('items')

        user = self.request.user
        if user.role != 'ADMIN':
            qs = qs.filter(created_by=user)

        branch      = self.request.query_params.get('branch')
        order_status = self.request.query_params.get('status')
        seller_id   = self.request.query_params.get('seller')
        customer_id = self.request.query_params.get('customer')
        from_date   = self.request.query_params.get('from_date')
        to_date     = self.request.query_params.get('to_date')

        if branch:
            qs = qs.filter(branch=branch)
        if order_status:
            qs = qs.filter(status=order_status)
        if seller_id:
            qs = qs.filter(seller__id=seller_id)
        if customer_id:
            qs = qs.filter(customer__id=customer_id)
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)

        return qs.order_by('-created_at')

    @action(detail=True, methods=['patch'], url_path='settle')
    @transaction.atomic
    def settle(self, request, pk=None):
        """
        PATCH /api/deposit-orders/{uuid}/settle/

        تسویه نهایی سفارش بیعانه:
        ۱. یک Sale جدید می‌سازد و به این بیعانه لینک می‌کند
        ۲. وضعیت بیعانه را DELIVERED می‌کند
        ۳. آمار مشتری را به‌روز می‌کند
        """
        order = self.get_object()

        if order.status == 'DELIVERED':
            return Response(
                {"error": "این سفارش قبلاً تسویه شده است."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if order.status == 'CANCELLED':
            return Response(
                {"error": "سفارش لغو شده قابل تسویه نیست."},
                status=status.HTTP_400_BAD_REQUEST
            )

        debt_payment_method = request.data.get('debt_payment_method')
        if not debt_payment_method:
            return Response(
                {"error": "نحوه پرداخت بدهی (debt_payment_method) الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        net_amount = Decimal(str(order.total_amount)) - Decimal(str(order.discount_amount))

        # ── ساخت فاکتور Sale ──
        sale = Sale.objects.create(
            branch            = order.branch,
            seller            = order.seller,
            customer          = order.customer,
            created_by        = request.user,
            total_amount      = net_amount,
            remaining_balance = Decimal('0.00'),
            description       = request.data.get(
                'description', f"تسویه سفارش بیعانه {order.id}"
            ),
        )

        # پرداخت بیعانه قبلی
        if order.deposit_paid > 0:
            Payment.objects.create(
                sale           = sale,
                payment_method = order.deposit_payment_method or 'OTHER',
                amount         = order.deposit_paid,
                description    = "بیعانه پرداخت‌شده قبلی",
            )

        # پرداخت بدهی
        if order.remaining_debt > 0:
            Payment.objects.create(
                sale           = sale,
                payment_method = debt_payment_method,
                amount         = order.remaining_debt,
                description    = "پرداخت بدهی هنگام تحویل",
            )

        # ── به‌روزرسانی بیعانه ──
        order.sale                = sale
        order.status              = 'DELIVERED'
        order.debt_payment_method = debt_payment_method
        order.deposit_paid        = net_amount   # کل مبلغ پرداخت شده
        order.save()             # remaining_debt خودکار صفر می‌شود

        # ── به‌روزرسانی آمار مشتری ──
        customer = Customer.objects.select_for_update().get(pk=order.customer_id)
        customer.last_purchase_date    = date.today()
        customer.total_purchase_amount += net_amount
        customer.last_purchase_type   = debt_payment_method
        customer.save()

        return Response(
            {
                "message":          "سفارش با موفقیت تسویه شد.",
                "sale_id":          str(sale.id),
                "deposit_order_id": str(order.id),
            },
            status=status.HTTP_200_OK
        )