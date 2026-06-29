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
    BRANCH_CHOICES, Mission, Role, ChecklistLog,
    Claim, ClaimFollowUp,DamageRegistration, ReturnRequest,
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
    MissionSerializer, RoleSerializer, ChecklistLogSerializer,
    ClaimSerializer, ClaimFollowUpSerializer,
    DamageRegistrationSerializer, ReturnRequestSerializer,
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
        
        # خروجی کامل لاگین شامل UUID، نام، فامیل و وضعیت تکمیل پروفایل
        return Response(
            {
                "access_token": access_token, 
                "roles": roles, 
                "branch": user.branch,
                "id": str(user.id),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_profile_completed": user.is_profile_completed
            },
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
    # خط permission_classes قبلی را حذف می‌کنیم و کنترل را به متد پایین می‌سپاریم

    # ─── مدیریت پویای سطح دسترسی بر اساس اکشن‌ها ───
    def get_permissions(self):
        # اکشن‌هایی که تمام کاربران لاگین شده باید به آن‌ها دسترسی داشته باشند
        public_actions = ['subordinates', 'update_branch', 'complete_profile']
        
        if self.action in public_actions:
            return [permissions.IsAuthenticated()]
            
        # برای بقیه متدها (مثل لیست کل کاربران، ساخت، حذف و ویرایش) فقط ادمین مجاز است
        return [IsAdminUser()]

    # ─── اکشن دریافت لیست کاربران زیردست ───
    @action(detail=False, methods=['get'], url_path='subordinates')
    def subordinates(self, request):
        current_user = request.user
        all_users = CustomUser.objects.prefetch_related('roles').all()
        
        # فیلتر کردن بر اساس منطق بالادستی مدل شما
        subordinate_users = [
            user for user in all_users 
            if current_user.is_superior_to(user) or current_user.is_superuser
        ]
        
        serializer = self.get_serializer(subordinate_users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ─── اکشن آپدیت شعبه کاربری که لاگین کرده ───
    @action(detail=False, methods=['patch'], url_path='update-branch')
    def update_branch(self, request):
        user = request.user
        new_branch = request.data.get('branch')

        valid_branches = [branch[0] for branch in BRANCH_CHOICES]

        if not new_branch or new_branch not in valid_branches:
            return Response(
                {"error": f"شعبه نامعتبر است. شعب مجاز: {', '.join(valid_branches)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.branch = new_branch
        user.save()

        return Response(
            {"message": "شعبه با موفقیت بروزرسانی شد.", "branch": user.branch},
            status=status.HTTP_200_OK
        )

    # ─── اکشن تکمیل پروفایل (نام و نام‌خانوادگی) توسط خود کاربر در اولین ورود ───
    @action(detail=False, methods=['patch'], url_path='complete-profile')
    def complete_profile(self, request):
        user = request.user
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')

        if not first_name or not last_name:
            return Response(
                {"error": "وارد کردن نام و نام خانوادگی الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.first_name = first_name
        user.last_name = last_name
        user.is_profile_completed = True
        user.save()

        return Response(
            {
                "message": "پروفایل شما با موفقیت تکمیل شد.",
                "first_name": user.first_name,
                "last_name": user.last_name
            },
            status=status.HTTP_200_OK
        )


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
        if debt_payment_method not in customer.purchase_types:
            customer.purchase_types = customer.purchase_types + [debt_payment_method]
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

        # ۱. مشخص کردن مأموریت‌های مجاز اولیه برای کاربر
        if user.is_superuser or 'ADMIN' in user_roles:
            qs = Mission.objects.all()
        else:
            all_users = CustomUser.objects.prefetch_related('roles').exclude(pk=user.pk)
            
            subordinate_ids = []
            for u in all_users:
                if user.is_superior_to(u):
                    subordinate_ids.append(u.id)

            qs = Mission.objects.filter(
                Q(assigned_to=user) |
                Q(created_by=user)  |
                Q(assigned_to_id__in=subordinate_ids)
            ).distinct()

        # ─── حل مشکل اصلی: اعمال فیلتر اختصاصی بر اساس پارامتر ارسالی فرانت ───
        assigned_to_param = self.request.query_params.get('assigned_to')
        if assigned_to_param:
            qs = qs.filter(assigned_to_id=assigned_to_param)

        return qs.order_by('-created_at')

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

        # ۱. مشخص کردن مجموعه اولیه چک‌لیست‌های مجاز برای این کاربر
        if user.is_superuser or 'ADMIN' in user_roles:
            qs = Checklist.objects.all()
        else:
            all_users = CustomUser.objects.prefetch_related('roles').exclude(pk=user.pk)
            subordinate_ids = [u.id for u in all_users if user.is_superior_to(u)]

            qs = Checklist.objects.filter(
                Q(assigned_to=user) |
                Q(created_by=user)  |
                Q(assigned_to_id__in=subordinate_ids)
            ).distinct()

        # ۲. اضافه کردن فیلتر اختصاصی بر اساس پارامتر ارسالی فرانت (مشکل اصلی اینجاست)
        assigned_to_param = self.request.query_params.get('assigned_to')
        if assigned_to_param:
            qs = qs.filter(assigned_to_id=assigned_to_param)

        return qs.order_by('-created_at')


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class   = TaskSerializer
    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        return user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())

    def _can_manage_task(self, user, task):
        if self._is_admin(user):
            return True
        if task.checklist.created_by == user:
            return True
        # FIX: اول چک کن assigned_to وجود داره
        if task.checklist.assigned_to is not None:
            return user.is_superior_to(task.checklist.assigned_to)
        return False


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
            # ─── حل مشکل: اضافه کردن completion_note به لیست فیلدهای مجاز ───
            forbidden_fields = {k for k in data if k not in ['is_completed', 'completion_note']}
            if forbidden_fields:
                raise PermissionDenied(
                    f"شما فقط مجاز به تغییر وضعیت انجام تسک و ثبت یادداشت هستید. "
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

class ChecklistLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    نمایش تاریخچه چک‌لیست‌ها.
    مدیران ارشد همه را می‌بینند.
    مدیران میانی لاگ‌های زیرمجموعه خود را می‌بینند.
    کارمندان فقط لاگ‌های خودشان را می‌بینند.
    """
    serializer_class = ChecklistLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # اگر ادمین اصلی است، همه لاگ‌ها را ببیند
        if user.is_superuser or user.roles.filter(code='ADMIN').exists():
            return ChecklistLog.objects.all().prefetch_related('items')
            
        # پیدا کردن کاربرانی که زیرمجموعه این شخص هستند
        # (با استفاده از متد is_superior_to که در مدل CustomUser نوشتی)
        subordinate_users = []
        all_users = CustomUser.objects.exclude(id=user.id)
        for u in all_users:
            if user.is_superior_to(u):
                subordinate_users.append(u.id)
        
        # لاگ‌های مربوط به خودش + لاگ‌های زیرمجموعه‌اش
        allowed_users = [user.id] + subordinate_users
        
        return ChecklistLog.objects.filter(
            assigned_to_id__in=allowed_users
        ).prefetch_related('items')
    
# ── Claims ────────────────────────────────────────────────────────────────────

class ClaimViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = Claim.objects.all().order_by('-created_at')
    serializer_class   = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        
        # فیلتر برای نمایش مطالبات پرداخت شده یا نشده در فرانت‌اند
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
            
        # فیلتر برای گرفتن مطالباتی که فقط به این شخص سپرده شده
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)

        return qs

    # اکشن اختصاصی برای اضافه کردن یک پیگیری جدید به مطالبه
    @action(detail=True, methods=['post'], url_path='add-follow-up')
    def add_follow_up(self, request, pk=None):
        claim = self.get_object()
        follow_up_type = request.data.get('follow_up_type')
        description    = request.data.get('description')

        if not follow_up_type or not description:
            return Response(
                {"error": "وارد کردن نوع پیگیری (follow_up_type) و توضیحات (description) الزامی است."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # ساخت رکورد پیگیری جدید و متصل کردنش به کاربر لاگین شده
        follow_up = ClaimFollowUp.objects.create(
            claim=claim,
            follower=request.user,
            follow_up_type=follow_up_type,
            description=description
        )
        
        serializer = ClaimFollowUpSerializer(follow_up)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
# ── Damage Registration ViewSet ───────────────────────────────────────────────
class DamageRegistrationViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = DamageRegistration.objects.all().order_by('-created_at')
    serializer_class   = DamageRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        
        # کارمندان عادی فقط ثبت‌های خودشان را می‌بینند اما ادمین همه را می‌بیند
        if not (user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())):
            qs = qs.filter(created_by=user)
        return qs


# ── Return Request ViewSet ────────────────────────────────────────────────────
class ReturnRequestViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = ReturnRequest.objects.all().order_by('-created_at')
    serializer_class   = ReturnRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        
        # فیلتر اختصاصی فرانت برای تفکیک در انتظارها و واریز شده‌ها
        # با ارسال پارامتر ?status=PENDING یا APPROVED یا COMPLETED
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
            
        return qs

    # ۱. اکشن تایید توسط مدیریت
    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        return_req = self.get_object()
        user = request.user
        
        # بررسی دسترسی: فقط ادمین یا مدیر مالی مجاز به تایید است
        has_permission = user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())
        if not has_permission:
            return Response({"error": "شما دسترسی تایید برگشتی را ندارید."}, status=status.HTTP_403_FORBIDDEN)
            
        if return_req.status != 'PENDING':
            return Response({"error": "این درخواست در وضعیت انتظار تایید مدیریت نیست."}, status=status.HTTP_400_BAD_REQUEST)
            
        return_req.is_approved = True
        return_req.status = 'APPROVED'
        return_req.save()
        
        return Response({"message": "درخواست برگشتی با موفقیت تایید شد. در انتظار واریز."}, status=status.HTTP_200_OK)

    # ۲. اکشن ثبت واریزی و تکمیل درخواست
    @action(detail=True, methods=['post'], url_path='finalize-refund')
    def finalize_refund(self, request, pk=None):
        return_req = self.get_object()
        user = request.user
        
        # دسترسی: مدیران مالی و ادمین و صندوق‌دار
        has_permission = user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER', 'CASHIER', 'ACCOUNTANT'] for r in user.roles.all())
        if not has_permission:
            return Response({"error": "شما دسترسی ثبت واریزی را ندارید."}, status=status.HTTP_403_FORBIDDEN)
            
        if return_req.status != 'APPROVED':
            return Response({"error": "این درخواست هنوز توسط مدیریت تایید نشده یا قبلاً واریز شده است."}, status=status.HTTP_400_BAD_REQUEST)
            
        refund_date   = request.data.get('refund_date')
        refund_method = request.data.get('refund_method')
        
        if not refund_date or not refund_method:
            return Response({"error": "ورود تاریخ واریز (refund_date) و روش واریز (refund_method) الزامی است."}, status=status.HTTP_400_BAD_REQUEST)
            
        return_req.refund_date   = refund_date
        return_req.refund_method = refund_method
        return_req.status        = 'COMPLETED'
        return_req.save()
        
        return Response({"message": "واریز ثبت شد و درخواست از لیست انتظار به لیست تکمیل‌شده‌ها منتقل شد."}, status=status.HTTP_200_OK)