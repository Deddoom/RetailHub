# -*- coding: utf-8 -*-
import datetime
from datetime import timedelta
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import ProtectedError, Q , F
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
    Claim, ClaimFollowUp, DamageRegistration, ReturnRequest,
    ReportDefinition, ReportSubmission,
    BranchTransfer, TransferItem, TransferLog,
    WasteReport, WasteItem, UserOnlineLog,
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
    ReportDefinitionSerializer, ReportSubmissionSerializer, ReportImageSerializer,
    BranchTransferSerializer, BranchTransferListSerializer,
    WasteReportSerializer, WasteReportListSerializer,
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
    queryset         = CustomUser.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer

    def get_permissions(self):
        public_actions = ['subordinates', 'update_branch', 'complete_profile', 'supervisors' , 'performance' , 'all_users_status']
        if self.action in public_actions:
            return [permissions.IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='subordinates')
    def subordinates(self, request):
        current_user = request.user

        if current_user.is_superuser or any(r.code == 'ADMIN' for r in current_user.roles.all()):
            subordinate_users = CustomUser.objects.exclude(pk=current_user.pk).prefetch_related('roles', 'superiors')
        else:
            subordinate_users_set = set()
            queue = list(current_user.subordinate_users.all())
            while queue:
                curr = queue.pop(0)
                if curr not in subordinate_users_set:
                    subordinate_users_set.add(curr)
                    queue.extend(curr.subordinate_users.all())
            subordinate_users = list(subordinate_users_set)

        serializer = self.get_serializer(subordinate_users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['patch'], url_path='update-branch')
    def update_branch(self, request):
        user       = request.user
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

    @action(detail=False, methods=['patch'], url_path='complete-profile')
    def complete_profile(self, request):
        user       = request.user
        first_name = request.data.get('first_name')
        last_name  = request.data.get('last_name')

        if not first_name or not last_name:
            return Response(
                {"error": "وارد کردن نام و نام خانوادگی الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.first_name          = first_name
        user.last_name           = last_name
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
    @action(detail=False, methods=['get'], url_path='supervisors')
    def supervisors(self, request):
        """
        دریافت لیست تمامی کاربرانی که نقش سرپرست (SUPERVISOR) دارند
        """
        supervisors = CustomUser.objects.filter(roles__code='SUPERVISOR', is_active=True).distinct()
        serializer = self.get_serializer(supervisors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='performance')
    def performance(self, request, pk=None):
        """
        دریافت آمار عملکرد کاربر (چک‌لیست‌ها، ماموریت‌ها و گزارش‌ها)
        پارامتر period می‌تواند یکی از مقادیر daily, weekly, monthly باشد. (پیش‌فرض: daily)
        """
        user = self.get_object()
        period = request.query_params.get('period', 'daily').lower()

        now = timezone.now()
        
        # تعیین بازه زمانی بر اساس درخواست
        if period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
        elif period == 'monthly':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
        else:
            return Response(
                {"error": "بازه زمانی نامعتبر است. مقادیر مجاز: daily, weekly, monthly"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        end_date = now + timedelta(days=1)

        # ── ۱. آمار ماموریت‌ها (Missions) ──
        total_missions = Mission.objects.filter(
            assigned_to=user, 
            created_at__gte=start_date, 
            created_at__lte=end_date
        ).count()
        
        completed_missions = Mission.objects.filter(
            assigned_to=user, 
            status='COMPLETED', 
            updated_at__gte=start_date, 
            updated_at__lte=end_date
        ).count()

        # ── ۲. آمار چک‌لیست‌ها (Checklists) ──
        # از روی لاگ‌های ثبت شده بررسی می‌شود که آیا کل تسک‌های آن لاگ برابر با تسک‌های انجام شده است یا خیر
        logs = ChecklistLog.objects.filter(
            assigned_to=user, 
            logged_at__gte=start_date, 
            logged_at__lte=end_date
        )
        total_checklists = logs.count()
        completed_checklists = logs.filter(
            total_tasks=F('completed_tasks'), 
            total_tasks__gt=0
        ).count()

        # ── ۳. آمار گزارش‌ها (Reports) ──
        total_reports = ReportDefinition.objects.filter(
            subordinate=user, 
            created_at__gte=start_date, 
            created_at__lte=end_date
        ).count()
        
        submitted_reports = ReportSubmission.objects.filter(
            submitted_by=user, 
            submitted_at__gte=start_date, 
            submitted_at__lte=end_date
        ).count()

        # ── خروجی نهایی ──
        return Response({
            "user_id": str(user.id),
            "name": user.get_full_name() or user.username,
            "period": period,
            "stats": {
                "missions": {
                    "total": total_missions,
                    "completed": completed_missions
                },
                "checklists": {
                    "total": total_checklists,
                    "completed": completed_checklists
                },
                "reports": {
                    "total": total_reports,
                    "submitted": submitted_reports
                }
            }
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='mark-online')
    def mark_online(self, request):
        """
        API برای اعلام آنلاین شدن کاربر در اپلیکیشن
        فرانت‌اند باید بدنه زیر را POST کند: {"status": 1}
        """
        status_val = request.data.get('status')
        if str(status_val) != '1':
            return Response(
                {"error": "برای ثبت حضور، فیلد status باید مقدار 1 داشته باشد."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.utils import timezone
        now = timezone.now()
        today = now.date()

        # get_or_create: اگر رکوردی برای امروز این کاربر نبود، می‌سازد. 
        # اگر بود، فقط آپدیتش می‌کند (به کمک last_seen که auto_now است).
        log, created = UserOnlineLog.objects.get_or_create(
            user=request.user,
            date=today,
            defaults={'first_seen': now}
        )
        
        # اگر رکورد از قبل وجود داشت (کاربر امروز قبلا هم آنلاین شده بود)، ساعت آخرین بازدید را آپدیت می‌کنیم
        if not created:
            log.save() # فیلد last_seen به صورت خودکار به لحظه فعلی آپدیت می‌شود

        return Response(
            {"message": "وضعیت آنلاین شما برای امروز ثبت شد.", "date": str(today), "time": now.strftime("%H:%M")},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='all-users-status')
    def all_users_status(self, request):
        """
        لیست همه کاربران فعال سیستم با اطلاعات پایه، آمار عملکرد و وضعیت آنلاین بودن
        """
        from django.db.models import Count, F
        from django.utils import timezone
        from datetime import timedelta

        period = request.query_params.get('period')
        now = timezone.now()
        today_date = now.date()
        start_date = None
        end_date = now + timedelta(days=1)

        if period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
        elif period == 'monthly':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
        elif period:
            return Response({"error": "بازه زمانی نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST)

        users_qs = CustomUser.objects.filter(is_active=True).prefetch_related('roles').order_by('branch', 'first_name')
        
        branch_param = request.query_params.get('branch')
        role_param   = request.query_params.get('role')

        if branch_param: users_qs = users_qs.filter(branch=branch_param)
        if role_param:   users_qs = users_qs.filter(roles__code=role_param).distinct()

        users = list(users_qs)
        user_ids = [u.id for u in users]

        if not user_ids:
            return Response([], status=status.HTTP_200_OK)

        missions_tot_qs = Mission.objects.filter(assigned_to_id__in=user_ids)
        missions_com_qs = Mission.objects.filter(assigned_to_id__in=user_ids, status='COMPLETED')
        checklists_tot_qs = ChecklistLog.objects.filter(assigned_to_id__in=user_ids)
        checklists_com_qs = ChecklistLog.objects.filter(assigned_to_id__in=user_ids, total_tasks=F('completed_tasks'), total_tasks__gt=0)
        reports_tot_qs = ReportDefinition.objects.filter(subordinate_id__in=user_ids)
        reports_sub_qs = ReportSubmission.objects.filter(submitted_by_id__in=user_ids)

        if start_date:
            missions_tot_qs = missions_tot_qs.filter(created_at__gte=start_date, created_at__lte=end_date)
            missions_com_qs = missions_com_qs.filter(updated_at__gte=start_date, updated_at__lte=end_date)
            checklists_tot_qs = checklists_tot_qs.filter(logged_at__gte=start_date, logged_at__lte=end_date)
            checklists_com_qs = checklists_com_qs.filter(logged_at__gte=start_date, logged_at__lte=end_date)
            reports_tot_qs = reports_tot_qs.filter(created_at__gte=start_date, created_at__lte=end_date)
            reports_sub_qs = reports_sub_qs.filter(submitted_at__gte=start_date, submitted_at__lte=end_date)

        missions_total = dict(missions_tot_qs.order_by().values_list('assigned_to_id').annotate(c=Count('id')))
        missions_completed = dict(missions_com_qs.order_by().values_list('assigned_to_id').annotate(c=Count('id')))
        checklists_total = dict(checklists_tot_qs.order_by().values_list('assigned_to_id').annotate(c=Count('id')))
        checklists_completed = dict(checklists_com_qs.order_by().values_list('assigned_to_id').annotate(c=Count('id')))
        reports_total = dict(reports_tot_qs.order_by().values_list('subordinate_id').annotate(c=Count('id')))
        reports_submitted = dict(reports_sub_qs.order_by().values_list('submitted_by_id').annotate(c=Count('id')))

        # --- واکشی لاگ آنلاین بودن کاربران در ۷ روز گذشته ---
        seven_days_ago = today_date - timedelta(days=6)
        online_logs_qs = UserOnlineLog.objects.filter(
            user_id__in=user_ids,
            date__gte=seven_days_ago,
            date__lte=today_date
        ).values('user_id', 'date', 'last_seen')

        from collections import defaultdict
        user_online_logs = defaultdict(dict)
        for log in online_logs_qs:
            user_online_logs[log['user_id']][log['date']] = log['last_seen']

        # ساخت لیست ۷ روز اخیر (از امروز به سمت گذشته)
        last_7_days = [today_date - timedelta(days=i) for i in range(7)]

        data = []
        for u in users:
            uid = u.id
            u_logs = user_online_logs.get(uid, {})
            
            # --- محاسبه وضعیت حضور غیاب ۷ روزه ---
            weekly_log = []
            online_count = 0
            is_online_today = False
            
            for d in last_7_days:
                if d in u_logs:
                    local_time = timezone.localtime(u_logs[d])
                    weekly_log.append({
                        "date": str(d),
                        "status": "آنلاین",
                        "time": local_time.strftime("%H:%M") # زمان دقیق آنلاین شدن در آن روز
                    })
                    online_count += 1
                    if d == today_date:
                        is_online_today = True
                else:
                    weekly_log.append({
                        "date": str(d),
                        "status": "آفلاین",
                        "time": None
                    })

            data.append({
                "id":         str(uid),
                "username":   u.username,
                "first_name": u.first_name,
                "last_name":  u.last_name,
                "full_name":  u.get_full_name() or u.username,
                "branch":     u.branch,
                "roles":      [{"code": r.code, "display": r.get_code_display()} for r in u.roles.all()],
                "is_active":  u.is_active,
                "attendance": {
                    "is_online_today": is_online_today,
                    "status_text": "امروز آنلاین شده" if is_online_today else "امروز آنلاین نشده",
                    "weekly_score": f"{online_count}/7",
                    "weekly_log": weekly_log
                },
                "stats": {
                    "missions": {
                        "total":     missions_total.get(uid, 0),
                        "completed": missions_completed.get(uid, 0),
                    },
                    "checklists": {
                        "total":     checklists_total.get(uid, 0),
                        "completed": checklists_completed.get(uid, 0),
                    },
                    "reports": {
                        "total":     reports_total.get(uid, 0),
                        "submitted": reports_submitted.get(uid, 0),
                    },
                },
            })

        return Response(data, status=status.HTTP_200_OK)

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

        # ✅ باگ ۱ رفع شد: هر دو روش پرداخت (بیعانه و بدهی) ادغام می‌شوند
        new_methods = [m for m in [order.deposit_payment_method, debt_payment_method] if m]
        customer.purchase_types = list(set(customer.purchase_types + new_methods))
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
        user       = self.request.user
        user_roles = set(user.roles.values_list('code', flat=True))

        if user.is_superuser or 'ADMIN' in user_roles:
            qs = Mission.objects.all()
        else:
            # ✅ رفع N+1: یک بار BFS بالا‌به‌پایین به جای N بار is_superior_to
            subordinate_ids = [u.id for u in user.get_all_subordinates()]

            qs = Mission.objects.filter(
                Q(assigned_to=user) |
                Q(created_by=user)  |
                Q(assigned_to_id__in=subordinate_ids)
            ).distinct()

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
        user       = self.request.user
        user_roles = set(user.roles.values_list('code', flat=True))

        if user.is_superuser or 'ADMIN' in user_roles:
            qs = Checklist.objects.all()
        else:
            # ✅ رفع N+1: یک بار BFS بالا‌به‌پایین به جای N بار is_superior_to
            subordinate_ids = [u.id for u in user.get_all_subordinates()]

            qs = Checklist.objects.filter(
                Q(assigned_to=user) |
                Q(created_by=user)  |
                Q(assigned_to_id__in=subordinate_ids)
            ).distinct()

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
        if task.checklist.assigned_to is not None:
            return user.is_superior_to(task.checklist.assigned_to)
        return False

    def get_queryset(self):
        user = self.request.user

        if self._is_admin(user):
            return Task.objects.select_related(
                'checklist', 'checklist__assigned_to', 'checklist__created_by'
            ).all()

        # ✅ رفع N+1: یک بار BFS بالا‌به‌پایین به جای N بار is_superior_to
        subordinate_ids = [u.id for u in user.get_all_subordinates()]

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


# ── ChecklistLog ──────────────────────────────────────────────────────────────

class ChecklistLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class   = ChecklistLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser or user.roles.filter(code='ADMIN').exists():
            qs = ChecklistLog.objects.all().prefetch_related('items')
        else:
            # ✅ رفع N+1: یک بار BFS بالا‌به‌پایین به جای N بار is_superior_to
            subordinate_ids = [u.id for u in user.get_all_subordinates()]
            allowed_users   = [user.id] + subordinate_ids
            qs = ChecklistLog.objects.filter(
                assigned_to_id__in=allowed_users
            ).prefetch_related('items')

        assigned_to_param = self.request.query_params.get('assigned_to')
        frequency_param   = self.request.query_params.get('frequency')
        from_date_param   = self.request.query_params.get('from_date')
        to_date_param     = self.request.query_params.get('to_date')

        if assigned_to_param: qs = qs.filter(assigned_to_id=assigned_to_param)
        if frequency_param:   qs = qs.filter(checklist_frequency=frequency_param)
        if from_date_param:   qs = qs.filter(period_start__gte=from_date_param)
        if to_date_param:     qs = qs.filter(period_end__lte=to_date_param)

        return qs.order_by('-logged_at')


# ── Claims ────────────────────────────────────────────────────────────────────

class ClaimViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    serializer_class   = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user     = self.request.user
        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())

        if is_admin:
            qs = Claim.objects.all().order_by('-created_at')
        else:
            # ✅ رفع N+1: یک بار BFS بالا‌به‌پایین به جای N بار is_superior_to
            subordinate_ids = [u.id for u in user.get_all_subordinates()]

            qs = Claim.objects.filter(
                Q(created_by=user) |
                Q(assigned_to=user) |
                Q(created_by_id__in=subordinate_ids) |
                Q(assigned_to_id__in=subordinate_ids)
            ).distinct().order_by('-created_at')

        status_param   = self.request.query_params.get('status')
        assigned_param = self.request.query_params.get('assigned_to')

        if status_param:   qs = qs.filter(status=status_param)
        if assigned_param: qs = qs.filter(assigned_to_id=assigned_param)

        return qs

    @action(detail=True, methods=['post'], url_path='add-follow-up')
    def add_follow_up(self, request, pk=None):
        claim          = self.get_object()
        follow_up_type = request.data.get('follow_up_type')
        description    = request.data.get('description')

        if not follow_up_type or not description:
            return Response(
                {"error": "وارد کردن نوع پیگیری (follow_up_type) و توضیحات (description) الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        follow_up = ClaimFollowUp.objects.create(
            claim=claim,
            follower=request.user,
            follow_up_type=follow_up_type,
            description=description
        )

        serializer = ClaimFollowUpSerializer(follow_up)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ── Damage Registration ───────────────────────────────────────────────────────

class DamageRegistrationViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = DamageRegistration.objects.all().order_by('-created_at')
    serializer_class   = DamageRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs   = super().get_queryset()
        user = self.request.user
        if not (user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())):
            qs = qs.filter(created_by=user)
        return qs


# ── Return Request ────────────────────────────────────────────────────────────

class ReturnRequestViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = ReturnRequest.objects.all().order_by('-created_at')
    serializer_class   = ReturnRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs           = super().get_queryset()
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        return_req = self.get_object()
        user       = request.user

        has_permission = user.is_superuser or any(
            r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all()
        )
        if not has_permission:
            return Response({"error": "شما دسترسی تایید برگشتی را ندارید."}, status=status.HTTP_403_FORBIDDEN)

        if return_req.status != 'PENDING':
            return Response({"error": "این درخواست در وضعیت انتظار تایید مدیریت نیست."}, status=status.HTTP_400_BAD_REQUEST)

        return_req.is_approved = True
        return_req.status      = 'APPROVED'
        return_req.save()

        return Response({"message": "درخواست برگشتی با موفقیت تایید شد. در انتظار واریز."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='finalize-refund')
    def finalize_refund(self, request, pk=None):
        return_req = self.get_object()
        user       = request.user

        has_permission = user.is_superuser or any(
            r.code in ['ADMIN', 'FINANCIAL_MANAGER', 'CASHIER', 'ACCOUNTANT'] for r in user.roles.all()
        )
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


# ── Report Definition ─────────────────────────────────────────────────────────

class ReportDefinitionViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    serializer_class   = ReportDefinitionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user     = self.request.user
        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())

        if is_admin:
            qs = ReportDefinition.objects.all()
        else:
            qs = ReportDefinition.objects.filter(
                Q(superior=user) | Q(subordinate=user)
            ).distinct()

        subordinate_param = self.request.query_params.get('subordinate')
        report_type_param = self.request.query_params.get('report_type')
        is_active_param   = self.request.query_params.get('is_active')

        if subordinate_param: qs = qs.filter(subordinate_id=subordinate_param)
        if report_type_param: qs = qs.filter(report_type=report_type_param)
        if is_active_param is not None:
            qs = qs.filter(is_active=(is_active_param.lower() == 'true'))

        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(superior=self.request.user)

    @action(detail=True, methods=['patch'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        definition = self.get_object()
        user       = request.user

        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())
        if not is_admin and definition.superior != user:
            return Response(
                {"error": "فقط سازنده گزارش می‌تواند وضعیت آن را تغییر دهد."},
                status=status.HTTP_403_FORBIDDEN
            )

        definition.is_active = not definition.is_active
        definition.save()
        return Response(
            {
                "message": f"گزارش {'فعال' if definition.is_active else 'غیرفعال'} شد.",
                "is_active": definition.is_active
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='duplicate')
    @transaction.atomic
    def duplicate(self, request, pk=None):
        """
        ایجاد یک گزارش جدید (فعال) از روی لاگ گزارش قدیمی (استفاده مجدد از موضوع)
        """
        original_definition = self.get_object()
        user = request.user

        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())
        if not is_admin and original_definition.superior != user:
            return Response(
                {"error": "شما دسترسی تکرار این گزارش را ندارید."},
                status=status.HTTP_403_FORBIDDEN
            )

        # امکان تغییر فرد زیردستی و مهلت در زمان کپی گرفتن وجود دارد
        new_subordinate_id = request.data.get('subordinate', original_definition.subordinate_id)
        new_deadline       = request.data.get('deadline')
        new_title          = request.data.get('title', original_definition.title)

        from core.models import CustomUser
        try:
            new_subordinate = CustomUser.objects.get(id=new_subordinate_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "کاربر زیردستی یافت نشد."}, status=status.HTTP_400_BAD_REQUEST)

        if not is_admin and not user.is_superior_to(new_subordinate):
            return Response({"error": "شما بالادست کاربر انتخاب شده نیستید."}, status=status.HTTP_403_FORBIDDEN)

        # ساخت گزارش جدید از روی الگوی قبلی
        new_definition = ReportDefinition.objects.create(
            superior=user,
            subordinate=new_subordinate,
            title=new_title,
            report_type=original_definition.report_type,
            interval=original_definition.interval,
            deadline=new_deadline,
            questions=original_definition.questions,
            is_active=True # گزارش جدید فوراً فعال و در کارتابل زیردستی قرار می‌گیرد
        )

        serializer = self.get_serializer(new_definition)
        return Response({
            "message": "گزارش با موفقیت مجدداً ایجاد و به زیردستی ارجاع داده شد.",
            "report": serializer.data
        }, status=status.HTTP_201_CREATED)


# ── Report Submission ─────────────────────────────────────────────────────────

class ReportSubmissionViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    serializer_class   = ReportSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user     = self.request.user
        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())

        if is_admin:
            qs = ReportSubmission.objects.select_related(
                'definition', 'submitted_by'
            ).prefetch_related('images').all()
        else:
            # بالادستی می‌تونه گزارش‌های همه زیردستانش رو ببینه
            subordinate_ids = [u.id for u in user.get_all_subordinates()]

            qs = ReportSubmission.objects.select_related(
                'definition', 'submitted_by'
            ).prefetch_related('images').filter(
                Q(definition__superior=user) |
                Q(submitted_by=user) |
                Q(submitted_by_id__in=subordinate_ids)
            ).distinct()

        definition_param   = self.request.query_params.get('definition')
        from_date_param    = self.request.query_params.get('from_date')
        to_date_param      = self.request.query_params.get('to_date')
        submitted_by_param = self.request.query_params.get('submitted_by')

        if definition_param:    qs = qs.filter(definition_id=definition_param)
        if from_date_param:     qs = qs.filter(submitted_at__date__gte=from_date_param)
        if to_date_param:       qs = qs.filter(submitted_at__date__lte=to_date_param)
        if submitted_by_param:  qs = qs.filter(submitted_by_id=submitted_by_param)

        return qs.order_by('-submitted_at')

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user     = request.user
        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())

        # ✅ باگ ۵ رفع شد: ادمین هم می‌تواند ویرایش کند
        if not is_admin and instance.submitted_by != user:
            return Response(
                {"error": "فقط ارسال‌کننده گزارش یا مدیر سیستم می‌تواند آن را ویرایش کند."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user     = request.user
        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())

        if not is_admin and instance.definition.superior != user:
            return Response(
                {"error": "شما دسترسی حذف این گزارش را ندارید."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)
    
# ── BranchTransfer ────────────────────────────────────────────────────────────
 
class BranchTransferViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    """
    انتقال بین شعب
 
    وضعیت‌ها:
      PENDING_SENDER   → ثبت درخواست توسط صندوقدار
      PENDING_RECEIVER → تایید سرپرست مبدا، در انتظار گیرنده
      APPROVED         → تایید هر دو سرپرست
      REJECTED         → رد شده (قابل ویرایش و بازارسال)
 
    اکشن‌ها:
      POST /transfers/{id}/approve_sender/  — تایید توسط سرپرست مبدا
      POST /transfers/{id}/reject_sender/   — رد توسط سرپرست مبدا
      POST /transfers/{id}/approve_receiver/— تایید توسط سرپرست مقصد
      POST /transfers/{id}/reject_receiver/ — رد توسط سرپرست مقصد
    """
    permission_classes = [permissions.IsAuthenticated]
 
    def get_serializer_class(self):
        if self.action == 'list':
            return BranchTransferListSerializer
        return BranchTransferSerializer
 
    def get_queryset(self):
        user = self.request.user
        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())
 
        if is_admin:
            qs = BranchTransfer.objects.all()
        else:
            qs = BranchTransfer.objects.filter(
                Q(source_cashier=user) |
                Q(sender_supervisor=user) |
                Q(receiver_supervisor=user)
            ).distinct()
 
        # فیلترهای اختیاری
        status_param = self.request.query_params.get('status')
        src_branch   = self.request.query_params.get('source_branch')
        dst_branch   = self.request.query_params.get('destination_branch')
        from_date    = self.request.query_params.get('from_date')
        to_date      = self.request.query_params.get('to_date')
 
        if status_param: qs = qs.filter(status=status_param)
        if src_branch:   qs = qs.filter(source_branch=src_branch)
        if dst_branch:   qs = qs.filter(destination_branch=dst_branch)
        if from_date:    qs = qs.filter(transfer_date__gte=from_date)
        if to_date:      qs = qs.filter(transfer_date__lte=to_date)
 
        return qs.select_related(
            'source_cashier', 'sender_supervisor', 'receiver_supervisor'
        ).prefetch_related('items', 'logs').order_by('-created_at')
 
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # فقط درخواست‌های رد شده یا در انتظار تایید مبدا قابل ویرایش‌اند
        if instance.status not in ['PENDING_SENDER', 'REJECTED']:
            return Response(
                {"error": "فقط انتقال‌هایی که در وضعیت 'رد شده' یا 'در انتظار تایید مبدا' هستند قابل ویرایش‌اند."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)
 
    @action(detail=True, methods=['post'], url_path='approve-sender')
    @transaction.atomic
    def approve_sender(self, request, pk=None):
        """تایید انتقال توسط سرپرست مبدا"""
        transfer = self.get_object()
 
        if transfer.status != 'PENDING_SENDER':
            return Response(
                {"error": "این انتقال در وضعیت 'در انتظار تایید مبدا' نیست."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if transfer.sender_supervisor != request.user and not (
            request.user.is_superuser or any(r.code == 'ADMIN' for r in request.user.roles.all())
        ):
            return Response(
                {"error": "فقط سرپرست مبدا یا ادمین می‌تواند این انتقال را تایید کند."},
                status=status.HTTP_403_FORBIDDEN
            )
 
        note = request.data.get('note', '')
        transfer.status      = 'PENDING_RECEIVER'
        transfer.sender_note = note
        transfer.save()
 
        TransferLog.objects.create(
            transfer=transfer,
            created_by=request.user,
            message=(
                f"انتقال توسط سرپرست مبدا ({request.user.get_full_name() or request.user.username}) تایید شد "
                f"و برای سرپرست مقصد ({transfer.receiver_supervisor.get_full_name() or transfer.receiver_supervisor.username}) ارسال گردید."
                + (f" توضیحات: {note}" if note else "")
            ),
        )
        return Response(
            {"message": "انتقال با موفقیت تایید شد و برای سرپرست مقصد ارسال گردید."},
            status=status.HTTP_200_OK
        )
 
    @action(detail=True, methods=['post'], url_path='reject-sender')
    @transaction.atomic
    def reject_sender(self, request, pk=None):
        """رد انتقال توسط سرپرست مبدا"""
        transfer = self.get_object()
 
        if transfer.status != 'PENDING_SENDER':
            return Response(
                {"error": "این انتقال در وضعیت 'در انتظار تایید مبدا' نیست."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if transfer.sender_supervisor != request.user and not (
            request.user.is_superuser or any(r.code == 'ADMIN' for r in request.user.roles.all())
        ):
            return Response(
                {"error": "فقط سرپرست مبدا یا ادمین می‌تواند این انتقال را رد کند."},
                status=status.HTTP_403_FORBIDDEN
            )
 
        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response(
                {"error": "ارسال دلیل عدم تایید (reason) الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        transfer.status           = 'REJECTED'
        transfer.rejection_reason = reason
        transfer.save()
 
        TransferLog.objects.create(
            transfer=transfer,
            created_by=request.user,
            message=(
                f"انتقال توسط سرپرست مبدا ({request.user.get_full_name() or request.user.username}) رد شد. "
                f"دلیل: {reason}"
            ),
        )
        return Response(
            {"message": "انتقال رد شد. صندوقدار می‌تواند پس از اصلاح، مجدداً ارسال کند."},
            status=status.HTTP_200_OK
        )
 
    @action(detail=True, methods=['post'], url_path='approve-receiver')
    @transaction.atomic
    def approve_receiver(self, request, pk=None):
        """تایید نهایی انتقال توسط سرپرست مقصد"""
        transfer = self.get_object()
 
        if transfer.status != 'PENDING_RECEIVER':
            return Response(
                {"error": "این انتقال در وضعیت 'در انتظار تایید مقصد' نیست."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if transfer.receiver_supervisor != request.user and not (
            request.user.is_superuser or any(r.code == 'ADMIN' for r in request.user.roles.all())
        ):
            return Response(
                {"error": "فقط سرپرست مقصد یا ادمین می‌تواند این انتقال را تایید کند."},
                status=status.HTTP_403_FORBIDDEN
            )
 
        note = request.data.get('note', '')
        transfer.status        = 'APPROVED'
        transfer.receiver_note = note
        transfer.save()
 
        # ساخت لاگ نهایی با تمام اطلاعات
        from django.utils import timezone as tz
        items_summary = ", ".join(
            f"{item.item_name} ({item.quantity} عدد)"
            for item in transfer.items.all()
        )
        TransferLog.objects.create(
            transfer=transfer,
            created_by=request.user,
            message=(
                f"در تاریخ {tz.now().strftime('%Y-%m-%d %H:%M')} انتقال با شناسه {transfer.id} "
                f"از شعبه {transfer.source_branch} به شعبه {transfer.destination_branch} "
                f"با راننده {transfer.driver_name} ثبت نهایی گردید. "
                f"اقلام: {items_summary}."
                + (f" توضیحات گیرنده: {note}" if note else "")
            ),
        )
        return Response(
            {"message": "فرایند انتقال با موفقیت ثبت نهایی شد."},
            status=status.HTTP_200_OK
        )
 
    @action(detail=True, methods=['post'], url_path='reject-receiver')
    @transaction.atomic
    def reject_receiver(self, request, pk=None):
        """رد انتقال توسط سرپرست مقصد"""
        transfer = self.get_object()
 
        if transfer.status != 'PENDING_RECEIVER':
            return Response(
                {"error": "این انتقال در وضعیت 'در انتظار تایید مقصد' نیست."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if transfer.receiver_supervisor != request.user and not (
            request.user.is_superuser or any(r.code == 'ADMIN' for r in request.user.roles.all())
        ):
            return Response(
                {"error": "فقط سرپرست مقصد یا ادمین می‌تواند این انتقال را رد کند."},
                status=status.HTTP_403_FORBIDDEN
            )
 
        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response(
                {"error": "ارسال دلیل عدم تایید (reason) الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        transfer.status           = 'REJECTED'
        transfer.rejection_reason = reason
        transfer.save()
 
        TransferLog.objects.create(
            transfer=transfer,
            created_by=request.user,
            message=(
                f"انتقال توسط سرپرست مقصد ({request.user.get_full_name() or request.user.username}) رد شد. "
                f"دلیل: {reason}"
            ),
        )
        return Response(
            {"message": "انتقال رد شد. صندوقدار می‌تواند پس از اصلاح، مجدداً ارسال کند."},
            status=status.HTTP_200_OK
        )
 
 
# ── WasteReport ───────────────────────────────────────────────────────────────
 
class WasteReportViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    """
    گزارش ضایعات (جایگزین DamageRegistration)
 
    وضعیت‌ها:
      PENDING                → ثبت توسط سرپرست، در انتظار انباردار
      APPROVED_BY_WAREHOUSE  → تایید انباردار، در انتظار مدیریت
      REJECTED_BY_WAREHOUSE  → رد توسط انباردار
      CLOSED                 → تعیین تکلیف توسط ادمین
 
    اکشن‌ها:
      POST /waste-reports/{id}/warehouse-review/ — بررسی انباردار
      POST /waste-reports/{id}/admin-decision/   — دستور مدیریت
    """
    permission_classes = [permissions.IsAuthenticated]
 
    def get_serializer_class(self):
        if self.action == 'list':
            return WasteReportListSerializer
        return WasteReportSerializer
 
    def get_queryset(self):
        user     = self.request.user
        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())
        is_warehouse = any(r.code == 'WAREHOUSE' for r in user.roles.all())
 
        if is_admin:
            # ادمین همه را می‌بیند
            qs = WasteReport.objects.all()
        elif is_warehouse:
            # انباردار همه گزارش‌ها را برای بررسی می‌بیند
            qs = WasteReport.objects.all()
        else:
            # سرپرست: گزارش‌های خودش + گزارش‌هایی که در آن‌ها دخیل بوده
            qs = WasteReport.objects.filter(
                Q(reporter=user) | Q(involved_users=user)
            ).distinct()
 
        # فیلترهای اختیاری
        status_param = self.request.query_params.get('status')
        branch_param = self.request.query_params.get('branch')
        from_date    = self.request.query_params.get('from_date')
        to_date      = self.request.query_params.get('to_date')
 
        if status_param: qs = qs.filter(status=status_param)
        if branch_param: qs = qs.filter(branch=branch_param)
        if from_date:    qs = qs.filter(waste_date__gte=from_date)
        if to_date:      qs = qs.filter(waste_date__lte=to_date)
 
        return qs.select_related(
            'reporter', 'warehouse_reviewer', 'admin_reviewer'
        ).prefetch_related('items', 'involved_users').order_by('-created_at')
 
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # فقط گزارش‌های در انتظار یا رد شده توسط انباردار قابل ویرایش توسط سرپرست هستند
        is_admin = request.user.is_superuser or any(r.code == 'ADMIN' for r in request.user.roles.all())
        if not is_admin and instance.status not in ['PENDING', 'REJECTED_BY_WAREHOUSE']:
            return Response(
                {"error": "گزارش پس از تایید انباردار قابل ویرایش نیست."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)
 
    @action(detail=True, methods=['post'], url_path='warehouse-review')
    @transaction.atomic
    def warehouse_review(self, request, pk=None):
        """
        بررسی انباردار: تایید یا رد گزارش ضایعات
 
        body:
          action  : 'approve' | 'reject'
          comment : توضیحات (اجباری برای رد، اختیاری برای تایید)
        """
        waste = self.get_object()
 
        is_admin     = request.user.is_superuser or any(r.code == 'ADMIN' for r in request.user.roles.all())
        is_warehouse = any(r.code == 'WAREHOUSE' for r in request.user.roles.all())
        if not is_admin and not is_warehouse:
            return Response(
                {"error": "فقط انباردار یا ادمین می‌تواند این عملیات را انجام دهد."},
                status=status.HTTP_403_FORBIDDEN
            )
 
        if waste.status != 'PENDING':
            return Response(
                {"error": "این گزارش قبلاً بررسی شده است."},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        action_type = request.data.get('action', '').strip()
        comment     = request.data.get('comment', '').strip()
 
        if action_type not in ['approve', 'reject']:
            return Response(
                {"error": "مقدار action باید 'approve' یا 'reject' باشد."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if action_type == 'reject' and not comment:
            return Response(
                {"error": "برای رد گزارش، ارسال توضیحات (comment) الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        waste.warehouse_reviewer = request.user
        waste.warehouse_comment  = comment
        waste.status = (
            'APPROVED_BY_WAREHOUSE' if action_type == 'approve'
            else 'REJECTED_BY_WAREHOUSE'
        )
        waste.save()
 
        if action_type == 'approve':
            msg = (
                f"گزارش ضایعات توسط انباردار ({request.user.get_full_name() or request.user.username}) تایید شد "
                f"و به مدیریت ارسال گردید."
                + (f" توضیحات: {comment}" if comment else "")
            )
        else:
            msg = (
                f"گزارش ضایعات توسط انباردار ({request.user.get_full_name() or request.user.username}) رد شد. "
                f"دلیل: {comment}"
            )
 
        return Response({"message": msg}, status=status.HTTP_200_OK)
 
    @action(detail=True, methods=['post'], url_path='admin-decision')
    @transaction.atomic
    def admin_decision(self, request, pk=None):
        """
        تعیین تکلیف توسط مدیریت (ادمین)
 
        body:
          instruction : دستور/توضیحات مدیریت (اجباری)
        """
        waste = self.get_object()
 
        is_admin = request.user.is_superuser or any(r.code == 'ADMIN' for r in request.user.roles.all())
        if not is_admin:
            return Response(
                {"error": "فقط ادمین می‌تواند دستور مدیریت صادر کند."},
                status=status.HTTP_403_FORBIDDEN
            )
 
        if waste.status != 'APPROVED_BY_WAREHOUSE':
            return Response(
                {"error": "این گزارش هنوز توسط انباردار تایید نشده یا قبلاً تعیین تکلیف شده است."},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        instruction = request.data.get('instruction', '').strip()
        if not instruction:
            return Response(
                {"error": "ارسال دستور مدیریت (instruction) الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        waste.admin_reviewer    = request.user
        waste.admin_instruction = instruction
        waste.status            = 'CLOSED'
        waste.save()
 
        return Response(
            {"message": "دستور مدیریت ثبت شد و فرایند رسیدگی به ضایعات مختومه گردید."},
            status=status.HTTP_200_OK
        )
