import os
import uuid
import datetime
from datetime import timedelta, date
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction, models
from django.db.models import ProtectedError, Q, F, Sum
from django.utils import timezone
from django.core.files.storage import default_storage
from decimal import Decimal
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
    WasteReport, WasteItem, UserOnlineLog, AdvanceRequest, AdvanceRequestLog,
    SellerCommissionConfig, SellerDailySale,
    LiquidityDailyRevenueSetting, LiquidityExpense, LiquidityExpensePayment, LiquidityCardTransaction,
    LiquidityDailyCharge,
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
    AdvanceRequestSerializer, AdvanceRequestListSerializer, AdvanceRequestInboxSerializer,
    SellerCommissionConfigSerializer, SellerDailySaleSerializer, SellerDailySaleBulkSerializer,
    LiquidityDailyRevenueSettingSerializer, LiquidityExpensePaymentSerializer,
    LiquidityCardTransactionSerializer, LiquidityExpenseSerializer, LiquidityExpenseListSerializer,
    FileUploadRequestSerializer, FileUploadResponseSerializer,
    LiquidityExpensePaymentCreateSerializer, LiquidityExpensePaymentCreateResponseSerializer,
    LiquidityExpenseActionResponseSerializer, LiquidityExpenseSummaryResponseSerializer,
    LiquidityCardTransactionCreateSerializer, LiquidityCardTransactionCreateResponseSerializer,
    LiquidityCardsOverviewSerializer, LiquidityCardDetailResponseSerializer,
    LiquiditySimpleMessageResponseSerializer,
    UserPendingCountsResponseSerializer, UserOnlineResponseSerializer,
    LiquidityDailyChargeSerializer, LiquidityDailyChargeCreateSerializer,
    AuthLoginRequestSerializer, AuthLoginResponseSerializer, BranchItemSerializer,
    UserDeleteResponseSerializer, UserRestoreResponseSerializer,
    BranchTransferNoteSerializer, BranchTransferRejectSerializer,
    ReturnRefundFinalizeSerializer, ReportDuplicateRequestSerializer,
    WasteReviewRequestSerializer, WasteDecisionRequestSerializer,
    AdvanceReviewRequestSerializer, AdvancePayRequestSerializer,
)
from core.pagination import OptionalPageNumberPagination
from drf_spectacular.utils import (
    extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes, OpenApiExample
)
from core.utils.jalali import (
    get_current_shamsi, get_days_in_shamsi_month, get_shamsi_month_name, format_jalali_date, get_gregorian_date
)
from core.utils.commission import calculate_seller_commission

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


# ── File / Image Upload ───────────────────────────────────────────────────────

@extend_schema(
    tags=['مدیریت فایل‌ها و رسانه'],
    summary="آپلود فایل یا تصویر",
    description="سرویس آپلود عکس و فایل (گزارش‌ها، فاکتورها، چک‌ها و ...). فایل را با کلید 'file' یا 'image' ارسال نمایید.",
    request={
        'multipart/form-data': FileUploadRequestSerializer,
    },
    responses={
        201: FileUploadResponseSerializer,
        400: OpenApiTypes.OBJECT,
    }
)
class FileUploadView(APIView):
    """
    سرویس آپلود عکس و فایل (گزارش‌ها، فاکتورها، چک‌ها و ...)
    ورودی: multipart/form-data با کلید 'file' یا 'image'
    خروجی: URL مستقیم و اطلاعات فایل
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        uploaded_file = request.FILES.get('file') or request.FILES.get('image')
        if not uploaded_file:
            return Response(
                {"error": "هیچ فایلی ارسال نشده است. لطفاً فایل را با کلید 'file' یا 'image' ارسال نمایید."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # حداکثر حجم فایل (۱۵ مگابایت)
        max_size_mb = 15
        if uploaded_file.size > max_size_mb * 1024 * 1024:
            return Response(
                {"error": f"حجم فایل بیش از حد مجاز است. حداکثر حجم مجاز {max_size_mb} مگابایت می‌باشد."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # اعتبارسنجی پسوند فایل
        original_name = uploaded_file.name
        ext = os.path.splitext(original_name)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.svg']
        if ext not in allowed_extensions:
            return Response(
                {"error": f"فرمت فایل نامعتبر است. فرمت‌های مجاز: {', '.join(allowed_extensions)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # مسیر ذخیره‌سازی با ساختار تاریخ و نام یکتا
        now = timezone.now()
        date_path = now.strftime("%Y/%m/%d")
        safe_basename = os.path.basename(original_name).replace(' ', '_')
        unique_name = f"{uuid.uuid4().hex[:10]}_{safe_basename}"
        file_relative_path = os.path.join('uploads', date_path, unique_name).replace('\\', '/')

        # ذخیره فایل در مدیا استوریج
        saved_path = default_storage.save(file_relative_path, uploaded_file)
        file_url = default_storage.url(saved_path)

        # ساخت URL کامل با هاست سرور یا BASE_URL تعیین‌شده
        base_url = os.environ.get('BASE_URL', '').strip().rstrip('/')
        if base_url:
            full_url = f"{base_url}{file_url}"
        else:
            full_url = request.build_absolute_uri(file_url)

        return Response(
            {
                "url": full_url,
                "image_url": full_url,
                "file_url": file_url,
                "filename": unique_name,
                "original_name": original_name,
                "size": uploaded_file.size,
                "content_type": getattr(uploaded_file, 'content_type', None),
            },
            status=status.HTTP_201_CREATED
        )


# ── Auth ──────────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['احراز هویت و دسترسی'],
    summary="ورود به سیستم و دریافت توکن JWT",
    description="ورود با نام کاربری یا شماره موبایل و رمز عبور. در صورت صحت اطلاعات، توکن دسترسی Stateless JWT و مشخصات نقش و کاربر بازگردانده می‌شود.",
    request=AuthLoginRequestSerializer,
    responses={
        200: AuthLoginResponseSerializer,
        400: OpenApiTypes.OBJECT,
        401: OpenApiTypes.OBJECT,
        403: OpenApiTypes.OBJECT,
    }
)
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

        if not user.is_active or user.is_deleted:
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

@extend_schema(
    tags=['شعب'],
    summary="لیست شعب تعریف‌شده در سیستم",
    description="دریافت لیست تمام شعب معتبر و ثبت‌شده در سیستم جهت استفاده در فیلترها و فرم‌های انتخاب شعبه.",
    responses={200: BranchItemSerializer(many=True)}
)
class BranchListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        branches = [{"value": v, "label": l} for v, l in BRANCH_CHOICES]
        return Response(branches, status=status.HTTP_200_OK)


# ── Users ─────────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['مدیریت کاربران'],
        summary="لیست کاربران سامانه با فیلتر و جستجو",
        description="دریافت لیست تمام کاربران فعال و غیرحذف‌شده سیستم. برای مشاهده کاربران حذف‌شده پارامتر include_deleted=true را ارسال نمایید.",
        parameters=[
            OpenApiParameter('include_deleted', OpenApiTypes.BOOL, OpenApiParameter.QUERY, description="نمایش کاربران حذف‌شده در لیست (پیش‌فرض: false)"),
            OpenApiParameter('search', OpenApiTypes.STR, OpenApiParameter.QUERY, description="جستجو در نام، نام خانوادگی و نام کاربری"),
            OpenApiParameter('role', OpenApiTypes.STR, OpenApiParameter.QUERY, description="فیلتر بر اساس کد نقش (مانند ADMIN, CASHIER, SUPERVISOR)"),
            OpenApiParameter('branch', OpenApiTypes.STR, OpenApiParameter.QUERY, description="فیلتر بر اساس نام شعبه"),
            OpenApiParameter('is_active', OpenApiTypes.BOOL, OpenApiParameter.QUERY, description="فیلتر بر اساس وضعیت فعال/غیرفعال بودن حساب"),
        ]
    ),
    retrieve=extend_schema(
        tags=['مدیریت کاربران'],
        summary="دریافت مشخصات کامل یک کاربر",
    ),
    create=extend_schema(
        tags=['مدیریت کاربران'],
        summary="ثبت کاربر جدید در سامانه",
    ),
    update=extend_schema(
        tags=['مدیریت کاربران'],
        summary="ویرایش کامل اطلاعات کاربر",
    ),
    partial_update=extend_schema(
        tags=['مدیریت کاربران'],
        summary="ویرایش جزئی اطلاعات کاربر",
    ),
    destroy=extend_schema(
        tags=['مدیریت کاربران'],
        summary="حذف هوشمند کاربر (پاکسازی کامل یا آرشیو نرم)",
        description="اگر کاربر سابقه وابسته نداشته باشد کلاً حذف می‌شود؛ در صورت داشتن سوابق فاکتور و حسابداری، حساب کاربر نرم حذف شده و نام کاربری‌اش برای استفاده مجدد آزاد می‌گردد.",
        responses={200: UserDeleteResponseSerializer}
    ),
)
class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        # صندوق‌داران و سایر پرسنل لاگین‌شده می‌توانند لیست و جزئیات کاربران و سرپرستان را مشاهده کنند
        public_actions = [
            'list', 'retrieve', 'subordinates', 'update_branch',
            'complete_profile', 'supervisors', 'performance',
            'all_users_status', 'mark_online', 'pending_counts', 'reports'
        ]
        if self.action in public_actions:
            return [permissions.IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return CustomUser.objects.none()

        qs = CustomUser.objects.all().prefetch_related('roles', 'superiors').order_by('-date_joined')

        role_param      = self.request.query_params.get('role')
        branch_param    = self.request.query_params.get('branch')
        is_active_param = self.request.query_params.get('is_active')
        search_param    = self.request.query_params.get('search')
        include_deleted = self.request.query_params.get('include_deleted', 'false').lower() == 'true'

        if self.action != 'restore' and not include_deleted:
            qs = qs.filter(is_deleted=False)

        if role_param:
            qs = qs.filter(roles__code=role_param)
        if branch_param:
            qs = qs.filter(branch=branch_param)
        if is_active_param is not None:
            qs = qs.filter(is_active=(is_active_param.lower() == 'true'))
        if search_param:
            qs = qs.filter(
                Q(username__icontains=search_param) |
                Q(original_username__icontains=search_param) |
                Q(first_name__icontains=search_param) |
                Q(last_name__icontains=search_param)
            )

        return qs.distinct()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # بررسی عدم حذف حساب کاربری خود ادمین/درخواست‌دهنده
        if instance.pk == request.user.pk:
            return Response(
                {"error": "شما نمی‌توانید حساب کاربری خودتان را حذف کنید."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if getattr(instance, 'is_deleted', False):
            return Response(
                {"message": "این کاربر قبلاً حذف شده است."},
                status=status.HTTP_200_OK
            )

        try:
            # ۱. تلاش برای حذف سخت (Hard Delete) در صورتی که کاربر هیچ سابقه وابسته‌ای نداشته باشد
            with transaction.atomic():
                instance.delete()
            return Response(
                {
                    "message": "کاربر بدون سابقه وابسته بوده و با موفقیت کلاً از سیستم پاک شد.",
                    "soft_deleted": False
                },
                status=status.HTTP_200_OK
            )
        except ProtectedError:
            # ۲. کاربر دارای سوابق و اسناد وابسته مالی/عملیاتی است -> حذف نرم هوشمند
            with transaction.atomic():
                now = timezone.now()
                timestamp = int(now.timestamp())
                old_username = instance.username

                instance.is_deleted = True
                instance.is_active = False
                instance.deleted_at = now
                instance.original_username = old_username
                # آزاد کردن نام کاربری برای استفاده و ثبت مجدد در آینده
                instance.username = f"deleted_{timestamp}_{old_username}"

                # قطع پیوندهای سلسله‌مراتبی
                instance.superiors.clear()
                instance.subordinate_users.clear()

                instance.save(update_fields=[
                    'is_deleted', 'is_active', 'deleted_at',
                    'original_username', 'username'
                ])

            return Response(
                {
                    "message": "کاربر با موفقیت حذف گردید (با توجه به وجود سوابق گذشته، اطلاعات کاربر به آرشیو منتقل، غیرفعال و نام کاربری برای استفاده مجدد آزاد شد).",
                    "soft_deleted": True
                },
                status=status.HTTP_200_OK
            )

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="بازیابی کاربر حذف شده",
        description="بازیابی کاربری که قبلاً به صورت نرم حذف شده است و بازگرداندن نام کاربری اصلی در صورت آزاد بودن آن.",
        responses={200: UserRestoreResponseSerializer, 400: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['post'], url_path='restore', permission_classes=[IsAdminUser])
    def restore(self, request, pk=None):
        instance = self.get_object()

        if not instance.is_deleted:
            return Response(
                {"error": "این کاربر حذف نشده است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        target_username = instance.original_username or instance.username
        if CustomUser.objects.filter(username=target_username).exclude(pk=instance.pk).exists():
            return Response(
                {"error": f"نام کاربری اصلی '{target_username}' هم‌اکنون توسط کاربر دیگری در حال استفاده است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            instance.is_deleted = False
            instance.is_active = True
            instance.deleted_at = None
            if instance.original_username:
                instance.username = instance.original_username
                instance.original_username = None
            instance.save(update_fields=['is_deleted', 'is_active', 'deleted_at', 'username', 'original_username'])

        return Response(
            {"message": "کاربر با موفقیت بازیابی شد.", "user": self.get_serializer(instance).data},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="دریافت لیست کاربران زیردست مستقیم",
        description="برای ادمین و مدیر مالی تمام کاربران سیستم، و برای سایر سرپرستان کاربران زیردست مستقیم نمایش داده می‌شوند.",
        responses={200: UserSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='subordinates')
    def subordinates(self, request):
        current_user = request.user

        # ادمین و مدیر مالی دسترسی کامل به تمام کاربران دارند
        if current_user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in current_user.roles.all()):
            subordinate_users = CustomUser.objects.filter(is_deleted=False).exclude(pk=current_user.pk).prefetch_related('roles', 'superiors')
        else:
            # سایر مدیران و بالادستی‌ها فقط و فقط یک لایه پایین‌تر (زیردستان مستقیم) را می‌بینند
            subordinate_users = current_user.subordinate_users.filter(is_deleted=False).prefetch_related('roles', 'superiors')

        serializer = self.get_serializer(subordinate_users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="تغییر شعبه کاربر جاری",
        description="بروزرسانی شعبه کاربر احراز هویت شده با یکی از شعب مجاز.",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT}
    )
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

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="تکمیل پروفایل (نام و نام خانوادگی)",
        description="تکمیل مشخصات اولیه پروفایل شامل نام و نام خانوادگی کاربر.",
        request=OpenApiTypes.OBJECT,
        responses={200: OpenApiTypes.OBJECT}
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

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="لیست سرپرستان فعال سیستم",
        description="دریافت لیست تمامی کاربرانی که نقش سرپرست (SUPERVISOR) فعال دارند.",
        responses={200: UserSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='supervisors')
    def supervisors(self, request):
        """
        دریافت لیست تمامی کاربرانی که نقش سرپرست (SUPERVISOR) دارند
        """
        supervisors = CustomUser.objects.filter(roles__code='SUPERVISOR', is_active=True, is_deleted=False).distinct()
        serializer = self.get_serializer(supervisors, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="آمار عملکرد کاربر (چک‌لیست‌ها، ماموریت‌ها و گزارش‌ها)",
        description="دریافت آمار عملکرد یک کاربر خاص بر اساس بازه زمانی روزانه، هفتگی یا ماهانه.",
        parameters=[
            OpenApiParameter('period', OpenApiTypes.STR, OpenApiParameter.QUERY, description="بازه زمانی: daily, weekly, monthly", enum=['daily', 'weekly', 'monthly'])
        ],
        responses={200: OpenApiTypes.OBJECT}
    )
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
        missions_in_period = Mission.objects.filter(
            assigned_to=user
        ).filter(
            Q(created_at__gte=start_date, created_at__lte=end_date) |
            Q(status='COMPLETED', updated_at__gte=start_date, updated_at__lte=end_date)
        ).distinct()
        
        total_missions = missions_in_period.count()
        completed_missions = missions_in_period.filter(
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

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="دریافت گزارشات یک کاربر خاص یا کاربر جاری (me)",
        description="شامل تمام تعاریف گزارش و ارسال‌های کاربر به همراه آمار تجمیعی. برای کاربر جاری از شناسه me استفاده کنید.",
        parameters=[
            OpenApiParameter('from_date', OpenApiTypes.DATE, OpenApiParameter.QUERY, description="فیلتر از تاریخ"),
            OpenApiParameter('to_date', OpenApiTypes.DATE, OpenApiParameter.QUERY, description="فیلتر تا تاریخ"),
            OpenApiParameter('report_type', OpenApiTypes.STR, OpenApiParameter.QUERY, description="نوع گزارش: RECURRING یا DEADLINE", enum=['RECURRING', 'DEADLINE']),
            OpenApiParameter('is_active', OpenApiTypes.BOOL, OpenApiParameter.QUERY, description="فیلتر وضعیت فعال بودن"),
            OpenApiParameter('definition_id', OpenApiTypes.UUID, OpenApiParameter.QUERY, description="شناسه تعریف گزارش خاص"),
        ],
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['get'], url_path='reports')
    def reports(self, request, pk=None):
        """
        دریافت گزارشات یک کاربر خاص (شامل تمام تعاریف گزارش و ارسال‌های کاربر به همراه آمار تجمیعی)
        URL: GET /api/users/{id}/reports/
        یا برای کاربر جاری: GET /api/users/me/reports/
        """
        if pk == 'me':
            target_user = request.user
        else:
            target_user = self.get_object()

        current_user = request.user

        is_admin = current_user.is_superuser or any(
            r.code == 'ADMIN' for r in current_user.roles.all()
        )
        is_self = current_user == target_user
        is_superior = current_user.is_superior_to(target_user)

        if not (is_admin or is_self or is_superior):
            return Response(
                {"error": "شما دسترسی به گزارش‌های این کاربر را ندارید."},
                status=status.HTTP_403_FORBIDDEN
            )

        # دریافت پارامترهای اختیاری فیلتر
        from_date     = request.query_params.get('from_date')
        to_date       = request.query_params.get('to_date')
        is_active     = request.query_params.get('is_active')
        report_type   = request.query_params.get('report_type')
        definition_id = request.query_params.get('definition_id')

        # ── ۱. تعاریف گزارش‌های محول‌شده به کاربر ──
        definitions_qs = ReportDefinition.objects.filter(
            subordinate=target_user
        ).select_related('superior', 'subordinate').order_by('-created_at')

        if is_active is not None:
            definitions_qs = definitions_qs.filter(is_active=(is_active.lower() == 'true'))
        if report_type:
            definitions_qs = definitions_qs.filter(report_type=report_type)
        if definition_id:
            definitions_qs = definitions_qs.filter(id=definition_id)
        if from_date:
            definitions_qs = definitions_qs.filter(created_at__date__gte=from_date)
        if to_date:
            definitions_qs = definitions_qs.filter(created_at__date__lte=to_date)

        # ── ۲. ارسال‌های ثبت‌شده توسط کاربر ──
        submissions_qs = ReportSubmission.objects.filter(
            submitted_by=target_user
        ).select_related('definition', 'submitted_by').prefetch_related('images').order_by('-submitted_at')

        if report_type:
            submissions_qs = submissions_qs.filter(definition__report_type=report_type)
        if definition_id:
            submissions_qs = submissions_qs.filter(definition_id=definition_id)
        if from_date:
            submissions_qs = submissions_qs.filter(submitted_at__date__gte=from_date)
        if to_date:
            submissions_qs = submissions_qs.filter(submitted_at__date__lte=to_date)

        # ── ۳. آمار محاسباتی تجمیعی ──
        from django.db.models import Count
        all_user_defs = ReportDefinition.objects.filter(subordinate=target_user)
        total_def_count = all_user_defs.count()
        active_def_count = all_user_defs.filter(is_active=True).count()
        inactive_def_count = total_def_count - active_def_count
        recurring_def_count = all_user_defs.filter(report_type='RECURRING').count()
        deadline_def_count = all_user_defs.filter(report_type='DEADLINE').count()
        total_sub_count = ReportSubmission.objects.filter(submitted_by=target_user).count()

        # سریالایز داده‌ها
        definitions_data = ReportDefinitionSerializer(definitions_qs, many=True, context={'request': request}).data
        submissions_data = ReportSubmissionSerializer(submissions_qs, many=True, context={'request': request}).data

        # افزودن تعداد سابمیشن‌های ثبت‌شده به هر تعریف گزارش
        sub_counts = {
            str(item['definition_id']): item['count']
            for item in ReportSubmission.objects.filter(submitted_by=target_user).values('definition_id').annotate(count=Count('id'))
        }
        for d in definitions_data:
            d['submissions_count'] = sub_counts.get(str(d['id']), 0)

        return Response({
            "user": {
                "id": str(target_user.id),
                "username": target_user.username,
                "first_name": target_user.first_name,
                "last_name": target_user.last_name,
                "full_name": target_user.get_full_name() or target_user.username,
                "branch": target_user.branch,
                "roles": [r.code for r in target_user.roles.all()],
            },
            "stats": {
                "total_definitions": total_def_count,
                "active_definitions": active_def_count,
                "inactive_definitions": inactive_def_count,
                "recurring_definitions": recurring_def_count,
                "deadline_definitions": deadline_def_count,
                "total_submissions": total_sub_count,
                "filtered_definitions_count": len(definitions_data),
                "filtered_submissions_count": len(submissions_data),
            },
            "report_definitions": definitions_data,
            "report_submissions": submissions_data,
        }, status=status.HTTP_200_OK)

    @staticmethod
    def _get_user_pending_counts(user):
        """
        محاسبه تعداد وظایف انجام‌نشده کاربر برای بج‌ها و داشبورد اولیه:
        1. ماموریت‌های انجام نشده (pending_missions_count): ماموریت‌های با وضعیت PENDING یا DOING
        2. چک‌لیست‌های پر نشده (incomplete_checklists_count): چک‌لیست‌های کاربر با حداقل یک تسک انجام‌نشده
        3. گزارش‌های کامل نشده (incomplete_reports_count): گزارش‌های فعال منتسب به کاربر که هنوز در دوره مقرر ارسال نشده‌اند
        """
        from django.utils import timezone
        from datetime import timedelta
        from core.models import Mission, Checklist, ReportDefinition

        now = timezone.now()
        today = now.date()

        # ۱. ماموریت‌های انجام نشده
        pending_missions_count = Mission.objects.filter(
            assigned_to=user,
            status__in=['PENDING', 'DOING']
        ).count()

        # ۲. چک‌لیست‌های پر نشده
        incomplete_checklists_count = Checklist.objects.filter(
            assigned_to=user,
            tasks__is_completed=False
        ).distinct().count()

        # ۳. گزارش‌های کامل نشده
        user_defs = ReportDefinition.objects.filter(subordinate=user, is_active=True)
        incomplete_reports_count = 0

        for rdef in user_defs:
            if rdef.report_type == 'DEADLINE':
                # گزارش‌های مهلت‌دار: آیا پاسخی ارسال شده؟
                has_sub = rdef.submissions.filter(submitted_by=user).exists()
                if not has_sub:
                    incomplete_reports_count += 1
            elif rdef.report_type == 'RECURRING':
                interval = rdef.interval or 'DAILY'
                if interval == 'DAILY':
                    has_sub = rdef.submissions.filter(
                        submitted_by=user,
                        submitted_at__date=today
                    ).exists()
                elif interval == 'WEEKLY':
                    has_sub = rdef.submissions.filter(
                        submitted_by=user,
                        submitted_at__date__gte=today - timedelta(days=6)
                    ).exists()
                elif interval == 'MONTHLY':
                    has_sub = rdef.submissions.filter(
                        submitted_by=user,
                        submitted_at__date__gte=today - timedelta(days=29)
                    ).exists()
                else:
                    has_sub = rdef.submissions.filter(
                        submitted_by=user,
                        submitted_at__date__gte=today - timedelta(days=59)
                    ).exists()

                if not has_sub:
                    incomplete_reports_count += 1

        return {
            "pending_missions_count": pending_missions_count,
            "incomplete_reports_count": incomplete_reports_count,
            "incomplete_checklists_count": incomplete_checklists_count,
        }

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="اعلام آنلاین شدن کاربر در اپلیکیشن همراه با دریافت آمار وظایف باز",
        description="ثبت حضور و زمان آخرین بازدید روزانه کاربر، و بازگرداندن تعداد ماموریت‌های انجام‌نشده، گزارش‌های کامل‌نشده و چک‌لیست‌های پرنشده",
        responses={200: UserOnlineResponseSerializer}
    )
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

        pending_counts = self._get_user_pending_counts(request.user)

        return Response(
            {
                "message": "وضعیت آنلاین شما برای امروز ثبت شد.",
                "date": str(today),
                "time": now.strftime("%H:%M"),
                **pending_counts
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="دریافت آمار وظایف انجام‌نشده کاربر جاری (بج‌ها و داشبورد اولیه)",
        description="تعداد ماموریت‌های باز، چک‌لیست‌های پرنشده و گزارش‌های کامل‌نشده",
        responses={200: UserPendingCountsResponseSerializer}
    )
    @action(detail=False, methods=['get'], url_path='pending-counts')
    def pending_counts(self, request):
        """
        دریافت آمار عددی وظایف باز کاربر بدون نیاز به ثبت آنلاین شدن مجدد
        """
        counts = self._get_user_pending_counts(request.user)
        return Response(counts, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['مدیریت کاربران'],
        summary="وضعیت و آمار لحظه‌ای تمام کاربران و لاگ حضور و غیاب ۷ روز اخیر",
        description="آمار جامع انجام ماموریت‌ها، چک‌لیست‌ها، گزارش‌ها و وضعیت آنلاین بودن روزانه کاربران فعال.",
        parameters=[
            OpenApiParameter('period', OpenApiTypes.STR, OpenApiParameter.QUERY, description="بازه زمانی آمار: daily, weekly, monthly", enum=['daily', 'weekly', 'monthly']),
            OpenApiParameter('branch', OpenApiTypes.STR, OpenApiParameter.QUERY, description="فیلتر بر اساس نام شعبه"),
            OpenApiParameter('role', OpenApiTypes.STR, OpenApiParameter.QUERY, description="فیلتر بر اساس کد نقش"),
        ],
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=False, methods=['get'], url_path='all-users-status')
    def all_users_status(self, request):
        from django.db.models import Count, F
        from django.utils import timezone
        from datetime import timedelta
        from collections import defaultdict

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

        users_qs = CustomUser.objects.filter(is_active=True, is_deleted=False).prefetch_related('roles').order_by('branch', 'first_name')

        branch_param = request.query_params.get('branch')
        role_param   = request.query_params.get('role')

        if branch_param: users_qs = users_qs.filter(branch=branch_param)
        if role_param:   users_qs = users_qs.filter(roles__code=role_param).distinct()

        users    = list(users_qs)
        user_ids = [u.id for u in users]

        if not user_ids:
            return Response([], status=status.HTTP_200_OK)

        # ── تابع کمکی برای aggregation صحیح ──────────────────────────────────
        def _agg(qs, group_field):
            return {
                str(x[group_field]): x['c']
                for x in qs.order_by().values(group_field).annotate(c=Count('id'))
                if x[group_field] is not None
            }

        # ── Querysetهای پایه ──────────────────────────────────────────────────
        missions_tot_qs   = Mission.objects.filter(assigned_to_id__in=user_ids)
        missions_com_qs   = Mission.objects.filter(assigned_to_id__in=user_ids, status='COMPLETED')

        # چک‌لیست: برای daily از Task فعلی بخون، برای weekly/monthly از ChecklistLog
        if period == 'daily':
            # وضعیت چک‌لیست‌های فعال امروز (از Task مستقیم)
            from core.models import Task
            checklists_tot_qs = Task.objects.filter(
                checklist__assigned_to_id__in=user_ids
            )
            checklists_com_qs = Task.objects.filter(
                checklist__assigned_to_id__in=user_ids,
                is_completed=True
            )
            checklist_group_field = 'checklist__assigned_to_id'
        else:
            # وضعیت از لاگ‌های ثبت‌شده (هفتگی/ماهانه)
            checklists_tot_qs = ChecklistLog.objects.filter(assigned_to_id__in=user_ids)
            checklists_com_qs = ChecklistLog.objects.filter(
                assigned_to_id__in=user_ids,
                total_tasks=F('completed_tasks'),
                total_tasks__gt=0
            )
            checklist_group_field = 'assigned_to_id'

        reports_def_qs = ReportDefinition.objects.filter(subordinate_id__in=user_ids, is_active=True)
        reports_sub_qs = ReportSubmission.objects.filter(submitted_by_id__in=user_ids)

        # ── اعمال فیلتر زمانی ────────────────────────────────────────────────
        if start_date:
            missions_tot_qs = missions_tot_qs.filter(
                Q(created_at__gte=start_date, created_at__lte=end_date) |
                Q(status='COMPLETED', updated_at__gte=start_date, updated_at__lte=end_date)
            ).distinct()
            missions_com_qs = missions_com_qs.filter(updated_at__gte=start_date,  updated_at__lte=end_date)
            if period != 'daily':
                checklists_tot_qs = checklists_tot_qs.filter(logged_at__gte=start_date, logged_at__lte=end_date)
                checklists_com_qs = checklists_com_qs.filter(logged_at__gte=start_date, logged_at__lte=end_date)
            reports_def_qs = reports_def_qs.filter(created_at__gte=start_date,   created_at__lte=end_date)
            reports_sub_qs = reports_sub_qs.filter(submitted_at__gte=start_date, submitted_at__lte=end_date)

        # ── ساخت dictهای آمار ────────────────────────────────────────────────
        missions_total       = _agg(missions_tot_qs,   'assigned_to_id')
        missions_completed   = _agg(missions_com_qs,   'assigned_to_id')
        checklists_total     = _agg(checklists_tot_qs,  checklist_group_field)
        checklists_completed = _agg(checklists_com_qs,  checklist_group_field)
        reports_total        = _agg(reports_def_qs,     'subordinate_id')
        reports_submitted    = _agg(reports_sub_qs,     'submitted_by_id')

        # ── لاگ آنلاین بودن (۷ روز گذشته) ───────────────────────────────────
        seven_days_ago = today_date - timedelta(days=6)
        online_logs_qs = UserOnlineLog.objects.filter(
            user_id__in=user_ids,
            date__gte=seven_days_ago,
            date__lte=today_date
        ).values('user_id', 'date', 'last_seen')

        user_online_logs = defaultdict(dict)
        for log in online_logs_qs:
            user_online_logs[log['user_id']][log['date']] = log['last_seen']

        last_7_days = [today_date - timedelta(days=i) for i in range(7)]

        data = []
        for u in users:
            uid     = u.id
            uid_str = str(uid)
            u_logs  = user_online_logs.get(uid, {})

            weekly_log      = []
            online_count    = 0
            is_online_today = False

            for d in last_7_days:
                if d in u_logs:
                    local_time = timezone.localtime(u_logs[d])
                    weekly_log.append({
                        "date":   str(d),
                        "status": "آنلاین",
                        "time":   local_time.strftime("%H:%M"),
                    })
                    online_count += 1
                    if d == today_date:
                        is_online_today = True
                else:
                    weekly_log.append({"date": str(d), "status": "آفلاین", "time": None})

            data.append({
                "id":         uid_str,
                "username":   u.username,
                "first_name": u.first_name,
                "last_name":  u.last_name,
                "full_name":  u.get_full_name() or u.username,
                "branch":     u.branch,
                "roles":      [{"code": r.code, "display": r.get_code_display()} for r in u.roles.all()],
                "is_active":  u.is_active,
                "attendance": {
                    "is_online_today": is_online_today,
                    "status_text":     "امروز آنلاین شده" if is_online_today else "امروز آنلاین نشده",
                    "weekly_score":    f"{online_count}/7",
                    "weekly_log":      weekly_log,
                },
                "stats": {
                    "missions": {
                        "total":     missions_total.get(uid_str, 0),
                        "completed": missions_completed.get(uid_str, 0),
                    },
                    "checklists": {
                        "total":     checklists_total.get(uid_str, 0),
                        "completed": checklists_completed.get(uid_str, 0),
                    },
                    "reports": {
                        "total":     reports_total.get(uid_str, 0),
                        "submitted": reports_submitted.get(uid_str, 0),
                    },
                },
            })

        return Response(data, status=status.HTTP_200_OK)

# ── Sellers ───────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(tags=['فروشندگان و پورسانت'], summary="لیست فروشندگان"),
    retrieve=extend_schema(tags=['فروشندگان و پورسانت'], summary="مشاهده جزئیات فروشنده"),
    create=extend_schema(tags=['فروشندگان و پورسانت'], summary="ثبت فروشنده جدید"),
    update=extend_schema(tags=['فروشندگان و پورسانت'], summary="ویرایش کامل فروشنده"),
    partial_update=extend_schema(tags=['فروشندگان و پورسانت'], summary="ویرایش جزئی فروشنده"),
    destroy=extend_schema(tags=['فروشندگان و پورسانت'], summary="حذف فروشنده"),
)
class SellerViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset         = Seller.objects.all()
    serializer_class = SellerSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'lookup']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUser()]

    @extend_schema(tags=['فروشندگان و پورسانت'], summary="لیست سریع فروشندگان جهت انتخاب در فرم‌ها")
    @action(detail=False, methods=['get'], url_path='lookup')
    def lookup(self, request):
        sellers    = self.get_queryset()
        serializer = SellerLookupSerializer(sellers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ── Customers ─────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['مشتریان'],
        summary="لیست مشتریان (پشتیبانی از صفحه‌بندی هوشمند و جستجو)",
        description="دریافت لیست مشتریان با پشتیبانی از اینفینیت اسکرول و جستجوی سروری. در صورت ارسال page صفحه‌بندی اعمال می‌شود و در غیر این صورت خروجی مانند نسخه قبل آرایه‌ای خواهد بود تا نسخه‌های قبلی اپ با مشکلی مواجه نشوند.",
        parameters=[
            OpenApiParameter('page', OpenApiTypes.INT, description="شماره صفحه (شروع از ۱)", required=False),
            OpenApiParameter('page_size', OpenApiTypes.INT, description="تعداد در هر صفحه (پیش‌فرض ۲۰، حداکثر ۱۰۰)", required=False),
            OpenApiParameter('search', OpenApiTypes.STR, description="جستجو در نام و شماره تماس مشتری", required=False),
            OpenApiParameter('ordering', OpenApiTypes.STR, description="مرتب‌سازی (مثلاً name, -last_purchase_date, -total_purchase_amount)", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['مشتریان'], summary="مشاهده جزئیات مشتری"),
    create=extend_schema(tags=['مشتریان'], summary="ثبت مشتری جدید"),
    update=extend_schema(tags=['مشتریان'], summary="ویرایش کامل مشتری"),
    partial_update=extend_schema(tags=['مشتریان'], summary="ویرایش جزئی مشتری"),
    destroy=extend_schema(tags=['مشتریان'], summary="حذف مشتری"),
)
class CustomerViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = Customer.objects.all().order_by('-last_purchase_date', '-id')
    serializer_class   = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class   = OptionalPageNumberPagination
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['name', 'phone']
    ordering_fields    = ['name', 'last_purchase_date', 'total_purchase_amount']
    ordering           = ['-last_purchase_date', '-id']


# ── Sales ─────────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['فروش و فاکتورها'],
        summary="لیست فاکتورهای فروش",
        parameters=[
            OpenApiParameter('branch', OpenApiTypes.STR, description="فیلتر بر اساس نام شعبه", required=False),
            OpenApiParameter('seller', OpenApiTypes.INT, description="فیلتر بر اساس شناسه فروشنده", required=False),
            OpenApiParameter('customer', OpenApiTypes.INT, description="فیلتر بر اساس شناسه مشتری", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="فیلتر از تاریخ میلادی (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="فیلتر تا تاریخ میلادی (YYYY-MM-DD)", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['فروش و فاکتورها'], summary="جزئیات فاکتور فروش"),
    create=extend_schema(tags=['فروش و فاکتورها'], summary="ثبت فاکتور فروش جدید"),
    update=extend_schema(tags=['فروش و فاکتورها'], summary="ویرایش کامل فاکتور فروش"),
    partial_update=extend_schema(tags=['فروش و فاکتورها'], summary="ویرایش جزئی فاکتور فروش"),
    destroy=extend_schema(tags=['فروش و فاکتورها'], summary="حذف فاکتور فروش"),
)
class SaleViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = Sale.objects.all()
    permission_classes = [IsOwnerOrAdminOnly]

    def get_serializer_class(self):
        return SaleListSerializer if self.action == 'list' else SaleSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Sale.objects.none()

        qs = Sale.objects.select_related(
            'seller', 'customer', 'created_by'
        ).prefetch_related('payments', 'payments__cheques', 'deposit_items')

        user = self.request.user
        if not (user and user.is_authenticated and (user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all()))):
            qs = qs.filter(created_by=user) if (user and user.is_authenticated) else qs.none()

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

@extend_schema_view(
    list=extend_schema(tags=['هزینه‌های عمومی'], summary="لیست هزینه‌های عمومی فروشگاه"),
    retrieve=extend_schema(tags=['هزینه‌های عمومی'], summary="جزئیات هزینه عمومی"),
    create=extend_schema(tags=['هزینه‌های عمومی'], summary="ثبت هزینه عمومی جدید"),
    update=extend_schema(tags=['هزینه‌های عمومی'], summary="ویرایش کامل هزینه عمومی"),
    partial_update=extend_schema(tags=['هزینه‌های عمومی'], summary="ویرایش جزئی هزینه عمومی"),
    destroy=extend_schema(tags=['هزینه‌های عمومی'], summary="حذف هزینه عمومی"),
)
class ExpenseViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = Expense.objects.all()
    serializer_class   = ExpenseSerializer
    permission_classes = [IsOwnerOrAdminOnly]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Expense.objects.none()

        qs   = Expense.objects.select_related('created_by').prefetch_related('cheques')
        user = self.request.user
        if not (user and user.is_authenticated):
            return Expense.objects.none()
        is_admin = user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())
        return qs if is_admin else qs.filter(created_by=user)


# ── DamageReport ──────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(tags=['خسارت و ضایعات'], summary="لیست گزارش‌های خسارت"),
    retrieve=extend_schema(tags=['خسارت و ضایعات'], summary="جزئیات گزارش خسارت"),
    create=extend_schema(tags=['خسارت و ضایعات'], summary="ثبت گزارش خسارت جدید"),
    update=extend_schema(tags=['خسارت و ضایعات'], summary="ویرایش کامل گزارش خسارت"),
    partial_update=extend_schema(tags=['خسارت و ضایعات'], summary="ویرایش جزئی گزارش خسارت"),
    destroy=extend_schema(tags=['خسارت و ضایعات'], summary="حذف گزارش خسارت"),
)
class DamageReportViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = DamageReport.objects.all()
    serializer_class   = DamageReportSerializer
    permission_classes = [IsOwnerOrAdminOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── ItemExit ──────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(tags=['انبار و خروج کالا'], summary="لیست مجوزهای خروج کالا"),
    retrieve=extend_schema(tags=['انبار و خروج کالا'], summary="جزئیات مجوز خروج کالا"),
    create=extend_schema(tags=['انبار و خروج کالا'], summary="ثبت مجوز خروج کالا"),
    update=extend_schema(tags=['انبار و خروج کالا'], summary="ویرایش کامل مجوز خروج کالا"),
    partial_update=extend_schema(tags=['انبار و خروج کالا'], summary="ویرایش جزئی مجوز خروج کالا"),
    destroy=extend_schema(tags=['انبار و خروج کالا'], summary="حذف مجوز خروج کالا"),
)
class ItemExitViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = ItemExit.objects.all()
    serializer_class   = ItemExitSerializer
    permission_classes = [IsOwnerOrAdminOnly]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── DepositOrders ─────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['سفارش‌های بیعانه'],
        summary="لیست سفارش‌های بیعانه",
        parameters=[
            OpenApiParameter('branch', OpenApiTypes.STR, description="فیلتر بر اساس نام شعبه", required=False),
            OpenApiParameter('status', OpenApiTypes.STR, description="فیلتر بر اساس وضعیت سفارش", required=False),
            OpenApiParameter('seller', OpenApiTypes.INT, description="فیلتر بر اساس شناسه فروشنده", required=False),
            OpenApiParameter('customer', OpenApiTypes.INT, description="فیلتر بر اساس شناسه مشتری", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="فیلتر از تاریخ میلادی (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="فیلتر تا تاریخ میلادی (YYYY-MM-DD)", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['سفارش‌های بیعانه'], summary="جزئیات سفارش بیعانه"),
    create=extend_schema(tags=['سفارش‌های بیعانه'], summary="ثبت سفارش بیعانه جدید"),
    update=extend_schema(tags=['سفارش‌های بیعانه'], summary="ویرایش کامل سفارش بیعانه"),
    partial_update=extend_schema(tags=['سفارش‌های بیعانه'], summary="ویرایش جزئی سفارش بیعانه"),
    destroy=extend_schema(tags=['سفارش‌های بیعانه'], summary="حذف سفارش بیعانه"),
)
class DepositOrderViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = DepositOrder.objects.all()
    permission_classes = [IsOwnerOrAdminOnly]

    def get_serializer_class(self):
        return DepositOrderListSerializer if self.action == 'list' else DepositOrderSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return DepositOrder.objects.none()

        qs = DepositOrder.objects.select_related(
            'customer', 'seller', 'created_by', 'sale'
        ).prefetch_related('items')

        user = self.request.user
        if not (user and user.is_authenticated and (user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all()))):
            qs = qs.filter(created_by=user) if (user and user.is_authenticated) else qs.none()

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

@extend_schema_view(
    list=extend_schema(
        tags=['ماموریت‌ها'],
        summary="لیست ماموریت‌ها",
        parameters=[
            OpenApiParameter('assigned_to', OpenApiTypes.UUID, description="فیلتر بر اساس شناسه کاربر مامور", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['ماموریت‌ها'], summary="مشاهده جزئیات ماموریت"),
    create=extend_schema(tags=['ماموریت‌ها'], summary="تعریف ماموریت جدید"),
    update=extend_schema(tags=['ماموریت‌ها'], summary="ویرایش کامل ماموریت"),
    partial_update=extend_schema(tags=['ماموریت‌ها'], summary="ویرایش جزئی ماموریت"),
    destroy=extend_schema(tags=['ماموریت‌ها'], summary="حذف ماموریت"),
)
class MissionViewSet(viewsets.ModelViewSet):
    queryset           = Mission.objects.all()
    serializer_class   = MissionSerializer
    permission_classes = [IsAuthenticated, IsSuperiorUser]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['title', 'description']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Mission.objects.none()

        user       = self.request.user
        if not (user and user.is_authenticated):
            return Mission.objects.none()
        user_roles = set(user.roles.values_list('code', flat=True))

        if user.is_superuser or any(r in user_roles for r in ['ADMIN']):
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
            changed_forbidden_fields = []
            for k, val in data.items():
                if k != 'status':
                    curr_val = getattr(instance, k, None)
                    if hasattr(curr_val, 'pk') and hasattr(val, 'pk'):
                        if curr_val.pk != val.pk:
                            changed_forbidden_fields.append(k)
                    elif curr_val != val:
                        changed_forbidden_fields.append(k)

            if changed_forbidden_fields:
                raise PermissionDenied(
                    f"شما فقط مجاز به تغییر وضعیت انجام ماموریت (status) هستید. "
                    f"فیلدهای غیرمجاز تغییریافته: {', '.join(sorted(changed_forbidden_fields))}"
                )
            if 'status' in data:
                instance.status = data['status']
                instance.save()
        else:
            raise PermissionDenied("شما دسترسی به ویرایش این ماموریت را ندارید.")


# ── Checklists ────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['چک‌لیست‌ها و وظایف'],
        summary="لیست چک‌لیست‌ها",
        parameters=[
            OpenApiParameter('assigned_to', OpenApiTypes.UUID, description="فیلتر بر اساس کاربر مسئول", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="مشاهده جزئیات چک‌لیست"),
    create=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="تعریف چک‌لیست جدید"),
    update=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="ویرایش کامل چک‌لیست"),
    partial_update=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="ویرایش جزئی چک‌لیست"),
    destroy=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="حذف چک‌لیست"),
)
class ChecklistViewSet(viewsets.ModelViewSet):
    queryset           = Checklist.objects.all()
    serializer_class   = ChecklistSerializer
    permission_classes = [IsAuthenticated, IsSuperiorUser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Checklist.objects.none()

        user       = self.request.user
        if not (user and user.is_authenticated):
            return Checklist.objects.none()
        user_roles = set(user.roles.values_list('code', flat=True))

        if user.is_superuser or any(r in user_roles for r in ['ADMIN']):
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

@extend_schema_view(
    list=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="لیست وظایف/تسک‌ها"),
    retrieve=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="مشاهده جزئیات وظیفه"),
    create=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="ثبت وظیفه جدید"),
    update=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="ویرایش کامل وظیفه یا ثبت انجام"),
    partial_update=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="ویرایش جزئی وظیفه"),
    destroy=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="حذف وظیفه"),
)
class TaskViewSet(viewsets.ModelViewSet):
    queryset           = Task.objects.all()
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
        if getattr(self, 'swagger_fake_view', False):
            return Task.objects.none()

        user = self.request.user
        if not (user and user.is_authenticated):
            return Task.objects.none()

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
            changed_forbidden_fields = []
            for k, val in data.items():
                if k not in ['is_completed', 'completion_note']:
                    curr_val = getattr(instance, k, None)
                    if hasattr(curr_val, 'pk') and hasattr(val, 'pk'):
                        if curr_val.pk != val.pk:
                            changed_forbidden_fields.append(k)
                    elif curr_val != val:
                        changed_forbidden_fields.append(k)

            if changed_forbidden_fields:
                raise PermissionDenied(
                    f"شما فقط مجاز به تغییر وضعیت انجام تسک و ثبت یادداشت هستید. "
                    f"فیلدهای غیرمجاز تغییریافته: {', '.join(sorted(changed_forbidden_fields))}"
                )
            if 'is_completed' in data:
                if data['is_completed'] is True:
                    instance.is_completed = True
                    instance.completed_by = user
                    instance.completed_at = timezone.now()
                else:
                    instance.is_completed = False
                    instance.completed_by = None
                    instance.completed_at = None
            if 'completion_note' in data:
                instance.completion_note = data['completion_note']
            instance.save()
        else:
            raise PermissionDenied("شما دسترسی به ویرایش این تسک را ندارید.")


# ── Roles ─────────────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(tags=['مدیریت کاربران'], summary="لیست نقش‌های سیستم"),
    retrieve=extend_schema(tags=['مدیریت کاربران'], summary="مشاهده جزئیات نقش"),
)
class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = Role.objects.all()
    serializer_class   = RoleSerializer
    permission_classes = [IsAdminUser]


# ── ChecklistLog ──────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['چک‌لیست‌ها و وظایف'],
        summary="لیست لاگ‌ها و تاریخچه انجام چک‌لیست‌ها",
        parameters=[
            OpenApiParameter('assigned_to', OpenApiTypes.UUID, description="فیلتر بر اساس شناسه کاربر مسئول", required=False),
            OpenApiParameter('frequency', OpenApiTypes.STR, description="فیلتر بر اساس دوره تناوب (DAILY, WEEKLY, MONTHLY)", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="از تاریخ بازه (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="تا تاریخ بازه (YYYY-MM-DD)", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['چک‌لیست‌ها و وظایف'], summary="مشاهده جزئیات لاگ چک‌لیست"),
)
class ChecklistLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = ChecklistLog.objects.all()
    serializer_class   = ChecklistLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ChecklistLog.objects.none()

        user = self.request.user
        if not (user and user.is_authenticated):
            return ChecklistLog.objects.none()

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

@extend_schema_view(
    list=extend_schema(
        tags=['مطالبات و پیگیری‌ها'],
        summary="لیست مطالبات معوق",
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description="فیلتر بر اساس وضعیت مطالبه", required=False),
            OpenApiParameter('assigned_to', OpenApiTypes.UUID, description="فیلتر بر اساس کاربر پیگیری‌کننده", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['مطالبات و پیگیری‌ها'], summary="مشاهده جزئیات مطالبه و پیگیری‌ها"),
    create=extend_schema(tags=['مطالبات و پیگیری‌ها'], summary="ثبت پرونده مطالبه جدید"),
    update=extend_schema(tags=['مطالبات و پیگیری‌ها'], summary="ویرایش کامل پرونده مطالبه"),
    partial_update=extend_schema(tags=['مطالبات و پیگیری‌ها'], summary="ویرایش جزئی پرونده مطالبه"),
    destroy=extend_schema(tags=['مطالبات و پیگیری‌ها'], summary="حذف پرونده مطالبه"),
)
class ClaimViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = Claim.objects.all()
    serializer_class   = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Claim.objects.none()

        user = self.request.user
        if not (user and user.is_authenticated):
            return Claim.objects.none()
        is_admin = user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())

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

    @extend_schema(
        tags=['مطالبات و پیگیری‌ها'],
        summary="ثبت اقدام پیگیری جدید برای یک مطالبه",
        request=ClaimFollowUpSerializer,
        responses={201: ClaimFollowUpSerializer}
    )
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

@extend_schema_view(
    list=extend_schema(
        tags=['خسارت و ضایعات'],
        summary="لیست ثبت‌های خسارت و ضایعات",
        parameters=[
            OpenApiParameter('branch', OpenApiTypes.STR, description="فیلتر بر اساس نام شعبه", required=False),
            OpenApiParameter('reason', OpenApiTypes.STR, description="فیلتر بر اساس علت ضایعات", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="از تاریخ ثبت (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="تا تاریخ ثبت (YYYY-MM-DD)", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['خسارت و ضایعات'], summary="مشاهده جزئیات ثبت خسارت"),
    create=extend_schema(tags=['خسارت و ضایعات'], summary="ثبت خسارت و اقلام ضایعات جدید"),
    update=extend_schema(tags=['خسارت و ضایعات'], summary="ویرایش کامل ثبت خسارت"),
    partial_update=extend_schema(tags=['خسارت و ضایعات'], summary="ویرایش جزئی ثبت خسارت"),
    destroy=extend_schema(tags=['خسارت و ضایعات'], summary="حذف ثبت خسارت"),
)
class DamageRegistrationViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = DamageRegistration.objects.all().order_by('-created_at')
    serializer_class   = DamageRegistrationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return DamageRegistration.objects.none()

        qs   = super().get_queryset()
        user = self.request.user
        if not (user and user.is_authenticated):
            return DamageRegistration.objects.none()

        # ادمین، مدیر مالی و انباردار دسترسی کامل به تمامی ثبت‌های ضایعات دارند
        if not (user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER', 'WAREHOUSE'] for r in user.roles.all())):
            qs = qs.filter(created_by=user)

        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch=branch)

        reason = self.request.query_params.get('reason')
        if reason:
            qs = qs.filter(reason=reason)

        from_date = self.request.query_params.get('from_date')
        if from_date:
            qs = qs.filter(date__gte=from_date)

        to_date = self.request.query_params.get('to_date')
        if to_date:
            qs = qs.filter(date__lte=to_date)

        return qs


# ── Return Request ────────────────────────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['برگشتی کالا و وجه'],
        summary="لیست درخواست‌های مرجوعی کالا",
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description="فیلتر وضعیت: PENDING, APPROVED, REJECTED, COMPLETED", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['برگشتی کالا و وجه'], summary="مشاهده جزئیات درخواست مرجوعی"),
    create=extend_schema(tags=['برگشتی کالا و وجه'], summary="ثبت درخواست مرجوعی جدید"),
    update=extend_schema(tags=['برگشتی کالا و وجه'], summary="ویرایش کامل درخواست مرجوعی"),
    partial_update=extend_schema(tags=['برگشتی کالا و وجه'], summary="ویرایش جزئی درخواست مرجوعی"),
    destroy=extend_schema(tags=['برگشتی کالا و وجه'], summary="حذف درخواست مرجوعی"),
)
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

    @extend_schema(
        tags=['برگشتی کالا و وجه'],
        summary="تایید درخواست برگشتی توسط مدیریت",
        request=None,
        responses={200: OpenApiTypes.OBJECT}
    )
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

    @extend_schema(
        tags=['برگشتی کالا و وجه'],
        summary="ثبت نهایی واریزی و عودت وجه به مشتری",
        request=ReturnRefundFinalizeSerializer,
        responses={200: OpenApiTypes.OBJECT}
    )
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

@extend_schema_view(
    list=extend_schema(
        tags=['گزارش‌های دوره‌ای و مهلت‌دار'],
        summary="لیست تعاریف الگوهای گزارش‌دهی",
        parameters=[
            OpenApiParameter('subordinate', OpenApiTypes.UUID, description="فیلتر بر اساس کاربر موظف (زیردستی)", required=False),
            OpenApiParameter('report_type', OpenApiTypes.STR, description="نوع گزارش (DAILY, WEEKLY, MONTHLY, ON_DEMAND)", required=False),
            OpenApiParameter('is_active', OpenApiTypes.BOOL, description="وضعیت فعال/غیرفعال بودن گزارش", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="مشاهده جزئیات الگوی گزارش"),
    create=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="تعریف الگوی گزارش‌دهی جدید برای زیردستی"),
    update=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="ویرایش کامل الگوی گزارش"),
    partial_update=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="ویرایش جزئی الگوی گزارش"),
    destroy=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="حذف الگوی گزارش"),
)
class ReportDefinitionViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = ReportDefinition.objects.all()
    serializer_class   = ReportDefinitionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ReportDefinition.objects.none()

        user     = self.request.user
        if not (user and user.is_authenticated):
            return ReportDefinition.objects.none()
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

    @extend_schema(
        tags=['گزارش‌های دوره‌ای و مهلت‌دار'],
        summary="تغییر وضعیت فعال/غیرفعال بودن یک الگوی گزارش",
        request=None,
        responses={200: OpenApiTypes.OBJECT}
    )
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

    @extend_schema(
        tags=['گزارش‌های دوره‌ای و مهلت‌دار'],
        summary="ایجاد مجدد گزارش از روی الگوی قبلی (تکرار موضوع)",
        request=ReportDuplicateRequestSerializer,
        responses={201: ReportDefinitionSerializer}
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

@extend_schema_view(
    list=extend_schema(
        tags=['گزارش‌های دوره‌ای و مهلت‌دار'],
        summary="لیست گزارش‌های ارسال‌شده توسط کارکنان",
        parameters=[
            OpenApiParameter('definition', OpenApiTypes.INT, description="فیلتر بر اساس شناسه الگوی گزارش", required=False),
            OpenApiParameter('submitted_by', OpenApiTypes.UUID, description="فیلتر بر اساس ارسال‌کننده", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="از تاریخ ثبت (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="تا تاریخ ثبت (YYYY-MM-DD)", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="مشاهده جزئیات و تصاویر گزارش ارسالی"),
    create=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="ارسال گزارش کاری و پیوست تصاویر"),
    update=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="ویرایش گزارش ارسالی"),
    partial_update=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="ویرایش جزئی گزارش ارسالی"),
    destroy=extend_schema(tags=['گزارش‌های دوره‌ای و مهلت‌دار'], summary="حذف گزارش ارسالی"),
)
class ReportSubmissionViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = ReportSubmission.objects.all()
    serializer_class   = ReportSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ReportSubmission.objects.none()

        user     = self.request.user
        if not (user and user.is_authenticated):
            return ReportSubmission.objects.none()
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

@extend_schema_view(
    list=extend_schema(
        tags=['حواله و انتقال بین شعب'],
        summary="لیست حواله‌ها و انتقال کالا بین شعب",
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description="فیلتر وضعیت (PENDING_SENDER, PENDING_RECEIVER, APPROVED, REJECTED)", required=False),
            OpenApiParameter('source_branch', OpenApiTypes.STR, description="شعبه مبدا", required=False),
            OpenApiParameter('destination_branch', OpenApiTypes.STR, description="شعبه مقصد", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="از تاریخ (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="تا تاریخ (YYYY-MM-DD)", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['حواله و انتقال بین شعب'], summary="مشاهده جزئیات کامل و لاگ‌های انتقال کالا"),
    create=extend_schema(tags=['حواله و انتقال بین شعب'], summary="ثبت درخواست انتقال کالای جدید بین شعب"),
    update=extend_schema(tags=['حواله و انتقال بین شعب'], summary="ویرایش انتقال کالا"),
    partial_update=extend_schema(tags=['حواله و انتقال بین شعب'], summary="ویرایش جزئی انتقال کالا"),
    destroy=extend_schema(tags=['حواله و انتقال بین شعب'], summary="حذف درخواست انتقال کالا"),
)
class BranchTransferViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = BranchTransfer.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return BranchTransferListSerializer
        return BranchTransferSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return BranchTransfer.objects.none()

        user = self.request.user
        if not (user and user.is_authenticated):
            return BranchTransfer.objects.none()
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

    @extend_schema(
        tags=['حواله و انتقال بین شعب'],
        summary="تایید انتقال توسط سرپرست مبدا",
        request=BranchTransferNoteSerializer,
        responses={200: OpenApiTypes.OBJECT}
    )
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

    @extend_schema(
        tags=['حواله و انتقال بین شعب'],
        summary="رد انتقال توسط سرپرست مبدا",
        request=BranchTransferRejectSerializer,
        responses={200: OpenApiTypes.OBJECT}
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

    @extend_schema(
        tags=['حواله و انتقال بین شعب'],
        summary="تایید نهایی انتقال توسط سرپرست مقصد",
        request=BranchTransferNoteSerializer,
        responses={200: OpenApiTypes.OBJECT}
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

    @extend_schema(
        tags=['حواله و انتقال بین شعب'],
        summary="رد انتقال توسط سرپرست مقصد",
        request=BranchTransferRejectSerializer,
        responses={200: OpenApiTypes.OBJECT}
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

@extend_schema_view(
    list=extend_schema(
        tags=['خسارت و ضایعات'],
        summary="لیست گزارش‌های ضایعات و اقلام اسقاطی",
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description="فیلتر وضعیت: PENDING, APPROVED_BY_WAREHOUSE, REJECTED_BY_WAREHOUSE, CLOSED", required=False),
            OpenApiParameter('branch', OpenApiTypes.STR, description="شعبه مورد نظر", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="از تاریخ ثبت ضایعات (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="تا تاریخ ثبت ضایعات (YYYY-MM-DD)", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['خسارت و ضایعات'], summary="مشاهده جزئیات کامل گزارش ضایعات و اقلام آن"),
    create=extend_schema(tags=['خسارت و ضایعات'], summary="ثبت گزارش ضایعات جدید توسط سرپرست"),
    update=extend_schema(tags=['خسارت و ضایعات'], summary="ویرایش گزارش ضایعات"),
    partial_update=extend_schema(tags=['خسارت و ضایعات'], summary="ویرایش جزئی گزارش ضایعات"),
    destroy=extend_schema(tags=['خسارت و ضایعات'], summary="حذف گزارش ضایعات"),
)
class WasteReportViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = WasteReport.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return WasteReportListSerializer
        return WasteReportSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return WasteReport.objects.none()

        user     = self.request.user
        if not (user and user.is_authenticated):
            return WasteReport.objects.none()

        is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())
        is_warehouse = any(r.code == 'WAREHOUSE' for r in user.roles.all())

        if is_admin or is_warehouse:
            qs = WasteReport.objects.all()
        else:
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

    @extend_schema(
        tags=['خسارت و ضایعات'],
        summary="بررسی، تایید یا رد گزارش ضایعات توسط انباردار",
        request=WasteReviewRequestSerializer,
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['post'], url_path='warehouse-review')
    @transaction.atomic
    def warehouse_review(self, request, pk=None):
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

    @extend_schema(
        tags=['خسارت و ضایعات'],
        summary="دستور و تعیین تکلیف نهایی ضایعات توسط مدیریت",
        request=WasteDecisionRequestSerializer,
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['post'], url_path='admin-decision')
    @transaction.atomic
    def admin_decision(self, request, pk=None):
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


# ── AdvanceRequest (درخواست مساعده) ──────────────────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['مساعده کارکنان'],
        summary="لیست درخواست‌های مساعده من",
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description="فیلتر وضعیت درخواست مساعده", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="از تاریخ ثبت (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="تا تاریخ ثبت (YYYY-MM-DD)", required=False),
        ]
    ),
    retrieve=extend_schema(tags=['مساعده کارکنان'], summary="مشاهده جزئیات کامل درخواست مساعده"),
    create=extend_schema(tags=['مساعده کارکنان'], summary="ثبت درخواست مساعده جدید"),
    update=extend_schema(tags=['مساعده کارکنان'], summary="ویرایش کامل درخواست مساعده"),
    partial_update=extend_schema(tags=['مساعده کارکنان'], summary="ویرایش جزئی درخواست مساعده"),
    destroy=extend_schema(tags=['مساعده کارکنان'], summary="حذف درخواست مساعده"),
)
class AdvanceRequestViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    queryset           = AdvanceRequest.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return AdvanceRequestListSerializer
        return AdvanceRequestSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return AdvanceRequest.objects.none()

        user = self.request.user
        if not (user and user.is_authenticated):
            return AdvanceRequest.objects.none()
        
        is_admin = user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())

        # ادمین و مدیر مالی همه درخواست‌ها را می‌بینند
        if is_admin:
            qs = AdvanceRequest.objects.all()
        else:
            # کاربر درخواست‌های خودش، و بالادستی فقط درخواست‌هایی که مستقیماً به خودش ارجاع داده شده (یا بدون بالادستی تعیین‌شده) را می‌بیند
            subordinate_ids = [u.id for u in user.get_all_subordinates()]
            qs = AdvanceRequest.objects.filter(
                Q(requester=user) | 
                Q(target_superior=user) | 
                (Q(target_superior__isnull=True) & Q(requester_id__in=subordinate_ids))
            ).distinct()

        # فیلترهای اختیاری وضعیت و تاریخ
        status_param = self.request.query_params.get('status')
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')

        if status_param: qs = qs.filter(status=status_param)
        if from_date:    qs = qs.filter(created_at__date__gte=from_date)
        if to_date:      qs = qs.filter(created_at__date__lte=to_date)

        return qs.select_related('requester', 'target_superior', 'superior_reviewer', 'admin_reviewer', 'finance_reviewer').prefetch_related('logs').order_by('-created_at')

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        
        # اگر کاربر بالادستی داشته باشد، وضعیت اولیه PENDING_SUPERIOR است
        has_superiors = user.superiors.exists()
        initial_status = 'PENDING_SUPERIOR' if has_superiors else 'PENDING_ADMIN'
        
        advance = serializer.save(requester=user, status=initial_status)
        
        if advance.target_superior:
            target_name = advance.target_superior.get_full_name() or advance.target_superior.username
            log_msg = f"درخواست مساعده به مبلغ {advance.amount} ثبت شد و به بالادستی ({target_name}) ارجاع داده شد."
        elif initial_status == 'PENDING_ADMIN':
            log_msg = f"درخواست مساعده به مبلغ {advance.amount} ثبت شد. (ارسال مستقیم به ادمین به دلیل نداشتن بالادستی)"
        else:
            log_msg = f"درخواست مساعده به مبلغ {advance.amount} ثبت شد."
            
        AdvanceRequestLog.objects.create(
            advance_request=advance, actor=user, action=log_msg
        )

    # --- ۱. بررسی بالادستی ---
    @extend_schema(
        tags=['مساعده کارکنان'],
        summary="بررسی و تایید یا رد درخواست مساعده توسط بالادستی",
        request=AdvanceReviewRequestSerializer,
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['post'], url_path='superior-review')
    @transaction.atomic
    def superior_review(self, request, pk=None):
        advance = self.get_object()
        user = request.user
        
        if advance.status != 'PENDING_SUPERIOR':
            return Response({"error": "این درخواست در وضعیت انتظار تایید بالادستی نیست."}, status=status.HTTP_400_BAD_REQUEST)
            
        is_admin = user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())
        if not is_admin:
            if advance.target_superior:
                if advance.target_superior != user:
                    return Response({"error": "این درخواست برای شما ارجاع داده نشده است."}, status=status.HTTP_403_FORBIDDEN)
            else:
                if not user.is_superior_to(advance.requester):
                    return Response({"error": "شما بالادست این کاربر نیستید."}, status=status.HTTP_403_FORBIDDEN)

        action_type = request.data.get('action') # 'approve' or 'reject'
        note = request.data.get('note', '')

        if action_type not in ['approve', 'reject']:
            return Response({"error": "فیلد action باید approve یا reject باشد."}, status=status.HTTP_400_BAD_REQUEST)
        if action_type == 'reject' and not note:
            return Response({"error": "برای رد درخواست، نوشتن توضیحات (note) الزامی است."}, status=status.HTTP_400_BAD_REQUEST)

        advance.superior_reviewer = user
        advance.superior_note = note
        advance.status = 'PENDING_ADMIN' if action_type == 'approve' else 'REJECTED_BY_SUPERIOR'
        advance.save()

        action_text = "تایید شد و به ادمین ارجاع داده شد." if action_type == 'approve' else f"رد شد. دلیل: {note}"
        actor_name = user.get_full_name() or user.username
        AdvanceRequestLog.objects.create(
            advance_request=advance, actor=user, action=f"بررسی بالادستی ({actor_name}): {action_text}"
        )

        return Response({"message": "عملیات با موفقیت ثبت شد."}, status=status.HTTP_200_OK)

    # --- ۲. بررسی ادمین ---
    @extend_schema(
        tags=['مساعده کارکنان'],
        summary="بررسی و تایید یا رد درخواست مساعده توسط مدیریت (ادمین)",
        request=AdvanceReviewRequestSerializer,
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['post'], url_path='admin-review')
    @transaction.atomic
    def admin_review(self, request, pk=None):
        advance = self.get_object()
        user = request.user
        
        if advance.status != 'PENDING_ADMIN':
            return Response({"error": "این درخواست در وضعیت انتظار تایید ادمین نیست."}, status=status.HTTP_400_BAD_REQUEST)
            
        is_admin = user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())
        if not is_admin:
            return Response({"error": "فقط ادمین سیستم به این بخش دسترسی دارد."}, status=status.HTTP_403_FORBIDDEN)

        action_type = request.data.get('action')
        note = request.data.get('note', '')

        if action_type not in ['approve', 'reject']:
            return Response({"error": "فیلد action باید approve یا reject باشد."}, status=status.HTTP_400_BAD_REQUEST)
        if action_type == 'reject' and not note:
            return Response({"error": "برای رد درخواست، نوشتن توضیحات الزامی است."}, status=status.HTTP_400_BAD_REQUEST)

        advance.admin_reviewer = user
        advance.admin_note = note
        advance.status = 'PENDING_FINANCE' if action_type == 'approve' else 'REJECTED_BY_ADMIN'
        advance.save()

        action_text = "تایید شد و به مدیر مالی ارجاع داده شد." if action_type == 'approve' else f"رد شد. دلیل: {note}"
        AdvanceRequestLog.objects.create(
            advance_request=advance, actor=user, action=f"بررسی ادمین: {action_text}"
        )

        return Response({"message": "عملیات ادمین با موفقیت ثبت شد."}, status=status.HTTP_200_OK)

    # --- ۳. پرداخت توسط مدیر مالی ---
    @extend_schema(
        tags=['مساعده کارکنان'],
        summary="ثبت واریز و پرداخت نهایی مساعده توسط مدیر مالی",
        request=AdvancePayRequestSerializer,
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['post'], url_path='finance-pay')
    @transaction.atomic
    def finance_pay(self, request, pk=None):
        advance = self.get_object()
        user = request.user
        
        if advance.status != 'PENDING_FINANCE':
            return Response({"error": "این درخواست در وضعیت انتظار پرداخت نیست."}, status=status.HTTP_400_BAD_REQUEST)
            
        is_finance = user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())
        if not is_finance:
            return Response({"error": "فقط مدیر مالی یا ادمین به این بخش دسترسی دارد."}, status=status.HTTP_403_FORBIDDEN)

        payment_date = request.data.get('payment_date')
        note = request.data.get('note', '')

        if not payment_date:
            return Response({"error": "وارد کردن تاریخ پرداخت (payment_date) الزامی است."}, status=status.HTTP_400_BAD_REQUEST)

        advance.finance_reviewer = user
        advance.finance_note = note
        advance.payment_date = payment_date
        advance.status = 'PAID'
        advance.save()

        AdvanceRequestLog.objects.create(
            advance_request=advance, actor=user, 
            action=f"مدیر مالی پرداخت را در تاریخ {payment_date} ثبت کرد." + (f" توضیحات: {note}" if note else "")
        )

        return Response({"message": "وضعیت پرداخت با موفقیت ثبت شد."}, status=status.HTTP_200_OK)

    # --- ۴. کارتابل بالادستی: درخواست‌هایی که مستقیماً به من ارجاع شده ---
    @extend_schema(
        tags=['مساعده کارکنان'],
        summary="کارتابل درخواست‌های مساعده ارجاع‌شده به کاربر جاری (بالادستی)",
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description="فیلتر وضعیت", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="از تاریخ ثبت (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="تا تاریخ ثبت (YYYY-MM-DD)", required=False),
            OpenApiParameter('search', OpenApiTypes.STR, description="جستجو در نام یا نام کاربری", required=False),
        ],
        responses={200: AdvanceRequestInboxSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='my-inbox')
    def my_inbox(self, request):
        """
        کارتابل اختصاصی بالادستی:
        فقط درخواست‌هایی که target_superior=me هستند برمی‌گردد.
        این endpoint برای بالادستی‌ها طراحی شده تا «inbox» خود را ببینند.
        """
        user = request.user

        qs = AdvanceRequest.objects.filter(target_superior=user)

        # فیلتر وضعیت
        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        # فیلتر تاریخ
        from_date = request.query_params.get('from_date')
        to_date   = request.query_params.get('to_date')
        if from_date: qs = qs.filter(created_at__date__gte=from_date)
        if to_date:   qs = qs.filter(created_at__date__lte=to_date)

        # فیلتر جستجو بر اساس نام یا نام کاربری درخواست‌کننده
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(requester__first_name__icontains=search) |
                Q(requester__last_name__icontains=search)  |
                Q(requester__username__icontains=search)
            )

        qs = qs.select_related('requester', 'target_superior').prefetch_related('logs').order_by('-created_at')

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = AdvanceRequestInboxSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = AdvanceRequestInboxSerializer(qs, many=True)
        return Response(serializer.data)

    # --- ۵. ویو کامل ادمین: همه درخواست‌ها با فیلترهای پیشرفته ---
    @extend_schema(
        tags=['مساعده کارکنان'],
        summary="لیست جامع کلیه درخواست‌های مساعده سیستم جهت مدیریت و مالی",
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description="فیلتر وضعیت", required=False),
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="از تاریخ ثبت (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="تا تاریخ ثبت (YYYY-MM-DD)", required=False),
            OpenApiParameter('search', OpenApiTypes.STR, description="جستجو در نام یا نام کاربری", required=False),
            OpenApiParameter('requester_id', OpenApiTypes.UUID, description="شناسه کاربر متقاضی", required=False),
            OpenApiParameter('superior_id', OpenApiTypes.UUID, description="شناسه کاربر بالادستی", required=False),
        ],
        responses={200: AdvanceRequestInboxSerializer(many=True)}
    )
    @action(detail=False, methods=['get'], url_path='admin-list')
    def admin_list(self, request):
        """
        لیست کامل درخواست‌های مساعده برای ادمین و مدیر مالی.
        پشتیبانی از فیلترهای: status, from_date, to_date, search (نام/یوزرنیم), superior_id, requester_id
        """
        user = request.user
        is_admin = user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())

        if not is_admin:
            return Response({"error": "دسترسی محدود است."}, status=status.HTTP_403_FORBIDDEN)

        qs = AdvanceRequest.objects.all()

        # فیلتر وضعیت
        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        # فیلتر تاریخ
        from_date = request.query_params.get('from_date')
        to_date   = request.query_params.get('to_date')
        if from_date: qs = qs.filter(created_at__date__gte=from_date)
        if to_date:   qs = qs.filter(created_at__date__lte=to_date)

        # جستجوی متنی روی نام/یوزرنیم درخواست‌کننده
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(requester__first_name__icontains=search) |
                Q(requester__last_name__icontains=search)  |
                Q(requester__username__icontains=search)
            )

        # فیلتر بر اساس ID درخواست‌کننده مشخص
        requester_id = request.query_params.get('requester_id')
        if requester_id:
            qs = qs.filter(requester_id=requester_id)

        # فیلتر بر اساس ID بالادستی مشخص
        superior_id = request.query_params.get('superior_id')
        if superior_id:
            qs = qs.filter(target_superior_id=superior_id)

        qs = qs.select_related(
            'requester', 'target_superior', 'superior_reviewer', 'admin_reviewer', 'finance_reviewer'
        ).prefetch_related('logs').order_by('-created_at')

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = AdvanceRequestInboxSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = AdvanceRequestInboxSerializer(qs, many=True)
        return Response(serializer.data)


# ── سیستم پورسانت و پاداش فروشندگان (Seller Commission & Reward) ──────────────

@extend_schema_view(
    list=extend_schema(tags=['فروشندگان و پورسانت'], summary="لیست قوانین پورسانت و پاداش"),
    retrieve=extend_schema(tags=['فروشندگان و پورسانت'], summary="مشاهده جزئیات تنظیمات پورسانت یک فروشنده"),
    create=extend_schema(tags=['فروشندگان و پورسانت'], summary="ثبت قوانین پورسانت جدید برای فروشنده"),
    update=extend_schema(tags=['فروشندگان و پورسانت'], summary="ویرایش کامل تنظیمات پورسانت"),
    partial_update=extend_schema(tags=['فروشندگان و پورسانت'], summary="ویرایش جزئی تنظیمات پورسانت"),
    destroy=extend_schema(tags=['فروشندگان و پورسانت'], summary="حذف تنظیمات پورسانت"),
)
class SellerCommissionConfigViewSet(viewsets.ModelViewSet):
    """
    مدیریت تنظیمات پورسانت و پاداش برای فروشندگان:
    - ایجاد و ویرایش فقط توسط ادمین یا بالادستی مستقیم فروشنده
    - مشاهده توسط ادمین، مدیر مالی، بالادستی و خود فروشنده
    - اکشن استعلام جامع وضعیت و محاسبه خودکار پورسانت
    """
    queryset = SellerCommissionConfig.objects.select_related(
        'seller', 'created_by', 'updated_by'
    ).all()
    serializer_class = SellerCommissionConfigSerializer
    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        return user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())

    def _is_admin_or_finance(self, user):
        return user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())

    def _can_manage_seller(self, user, seller):
        if self._is_admin(user):
            return True
        return user.is_superior_to(seller)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset.none()

        user = self.request.user
        if not (user and user.is_authenticated):
            return self.queryset.none()

        if self._is_admin_or_finance(user):
            return self.queryset

        # برای سایر کاربران: اگر خود فروشنده است، یا بالادستی فروشنده است
        seller_ids = [
            u.id for u in CustomUser.objects.filter(roles__code='SELLER_STAFF', is_deleted=False)
            if user.is_superior_to(u) or u.pk == user.pk
        ]
        return self.queryset.filter(seller_id__in=seller_ids)

    def perform_create(self, serializer):
        user = self.request.user
        seller = serializer.validated_data.get('seller')

        if not self._can_manage_seller(user, seller):
            raise PermissionDenied("تنها ادمین یا بالادستی مستقیم فروشنده مجاز به تعریف سیستم پورسانت هستند.")

        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance

        if not self._can_manage_seller(user, instance.seller):
            raise PermissionDenied("تنها ادمین یا بالادستی مستقیم فروشنده مجاز به ویرایش سیستم پورسانت هستند.")

        serializer.save(updated_by=user)

    def perform_destroy(self, instance):
        user = self.request.user
        if not self._can_manage_seller(user, instance.seller):
            raise PermissionDenied("تنها ادمین یا بالادستی مستقیم فروشنده مجاز به حذف این رکورد هستند.")
        instance.delete()

    @extend_schema(
        tags=['فروشندگان و پورسانت'],
        summary="استعلام جامع وضعیت پورسانت، پاداش و فروش‌های ماهانه فروشنده",
        parameters=[
            OpenApiParameter(
                name='seller', type=OpenApiTypes.UUID, location=OpenApiParameter.QUERY,
                required=True, description="شناسه کاربر فروشنده"
            ),
            OpenApiParameter(
                name='shamsi_year', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
                required=False, description="سال شمسی (پیش‌فرض: سال جاری)"
            ),
            OpenApiParameter(
                name='shamsi_month', type=OpenApiTypes.INT, location=OpenApiParameter.QUERY,
                required=False, description="ماه شمسی (پیش‌فرض: ماه جاری، بین ۱ تا ۱۲)"
            ),
        ]
    )
    @action(detail=False, methods=['get'], url_path='status')
    def status(self, request):
        """
        استعلام جامع وضعیت پورسانت فروشنده به ازای ماه و سال شمسی مشخص.
        پارامترها:
        - seller: شناسه کاربری فروشنده (الزامی)
        - shamsi_year: سال شمسی (اختیاری - پیش‌فرض سال جاری)
        - shamsi_month: ماه شمسی (اختیاری - پیش‌فرض ماه جاری)
        """
        user = request.user
        seller_id = request.query_params.get('seller')

        if not seller_id:
            return Response(
                {"error": "پارامتر seller (شناسه کاربر فروشنده) الزامی است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            seller = CustomUser.objects.prefetch_related('roles', 'superiors').get(pk=seller_id)
        except (CustomUser.DoesNotExist, ValueError):
            return Response(
                {"error": "فروشنده مورد نظر یافت نشد."},
                status=status.HTTP_404_NOT_FOUND
            )

        # بررسی دسترسی خواندن وضعیت:
        # ادمین، مدیر مالی، بالادستی فروشنده، صندوق‌دار همان شعبه، یا خود فروشنده
        is_self = (user.pk == seller.pk)
        is_superior = user.is_superior_to(seller)
        is_admin_or_fin = self._is_admin_or_finance(user)
        is_branch_cashier = (
            any(r.code == 'CASHIER' for r in user.roles.all()) and
            user.branch and user.branch == seller.branch
        )

        if not (is_admin_or_fin or is_superior or is_self or is_branch_cashier):
            raise PermissionDenied("شما دسترسی لازم برای مشاهده وضعیت پورسانت این فروشنده را ندارید.")

        # تشخیص سال و ماه شمسی
        cur_y, cur_m, _ = get_current_shamsi()
        try:
            shamsi_year = int(request.query_params.get('shamsi_year', cur_y))
            shamsi_month = int(request.query_params.get('shamsi_month', cur_m))
        except ValueError:
            return Response(
                {"error": "سال یا ماه شمسی نامعتبر است."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not (1 <= shamsi_month <= 12):
            return Response(
                {"error": "ماه شمسی باید بین ۱ تا ۱۲ باشد."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # استخراج لیست فروش‌های روزانه ثبت شده برای این ماه
        daily_sales_qs = SellerDailySale.objects.filter(
            seller=seller,
            shamsi_year=shamsi_year,
            shamsi_month=shamsi_month
        ).select_related('recorded_by').order_by('shamsi_day')

        total_monthly_sales = sum(s.amount for s in daily_sales_qs)

        # استخراج کانفیگ پورسانت
        config = SellerCommissionConfig.objects.filter(seller=seller).first()

        # اجرای محاسبات پورسانت و پاداش
        calc_result = calculate_seller_commission(config, total_monthly_sales)

        try:
            days_in_month = get_days_in_shamsi_month(shamsi_year, shamsi_month)
        except Exception:
            days_in_month = 30

        response_data = {
            "seller": {
                "id": str(seller.id),
                "username": seller.username,
                "name": f"{seller.first_name} {seller.last_name}".strip() or seller.username,
                "branch": seller.branch,
            },
            "period": {
                "shamsi_year": shamsi_year,
                "shamsi_month": shamsi_month,
                "shamsi_month_name": get_shamsi_month_name(shamsi_month),
                "days_in_month": days_in_month,
            },
            "is_configured": calc_result["is_configured"],
            "config": SellerCommissionConfigSerializer(config).data if config else None,
            "sales_summary": {
                "total_monthly_sales": float(total_monthly_sales),
                "recorded_days_count": daily_sales_qs.count(),
                "daily_sales": [
                    {
                        "id": str(s.id),
                        "day": s.shamsi_day,
                        "amount": float(s.amount),
                        "shamsi_date": format_jalali_date(s.shamsi_year, s.shamsi_month, s.shamsi_day),
                        "recorded_by": s.recorded_by.username if s.recorded_by else None,
                        "recorded_by_name": f"{s.recorded_by.first_name} {s.recorded_by.last_name}".strip() if s.recorded_by else None,
                        "notes": s.notes,
                        "updated_at": s.updated_at
                    }
                    for s in daily_sales_qs
                ]
            },
            "calculation": calc_result
        }

        return Response(response_data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(tags=['فروشندگان و پورسانت'], summary="لیست فروش‌های روزانه فروشندگان"),
    retrieve=extend_schema(tags=['فروشندگان و پورسانت'], summary="مشاهده یک رکورد فروش روزانه"),
    create=extend_schema(tags=['فروشندگان و پورسانت'], summary="ثبت یک رکورد فروش روزانه برای فروشنده"),
    update=extend_schema(tags=['فروشندگان و پورسانت'], summary="ویرایش فروش روزانه"),
    partial_update=extend_schema(tags=['فروشندگان و پورسانت'], summary="ویرایش جزئی فروش روزانه"),
    destroy=extend_schema(tags=['فروشندگان و پورسانت'], summary="حذف رکورد فروش روزانه"),
)
class SellerDailySaleViewSet(viewsets.ModelViewSet):
    """
    ثبت و ویرایش لیست فروش روزانه فروشندگان در ماه‌های شمسی:
    - ایجاد/ویرایش توسط صندوق‌دار شعبه، بالادستی فروشنده یا ادمین
    - پشتیبانی از اکشن bulk-save برای ثبت کل روزهای ماه در یک درخواست
    """
    queryset = SellerDailySale.objects.select_related(
        'seller', 'recorded_by'
    ).all()
    serializer_class = SellerDailySaleSerializer
    permission_classes = [IsAuthenticated]

    def _can_record_sales_for_seller(self, user, seller):
        # ادمین و مدیر مالی دسترسی کامل دارند
        if user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all()):
            return True
        # بالادستی فروشنده
        if user.is_superior_to(seller):
            return True
        # صندوق‌دار همان شعبه فروشنده
        if any(r.code == 'CASHIER' for r in user.roles.all()) and user.branch and user.branch == seller.branch:
            return True
        return False

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return self.queryset.none()

        qs = self.queryset
        user = self.request.user
        if not (user and user.is_authenticated):
            return self.queryset.none()

        # فیلترها
        seller_id = self.request.query_params.get('seller')
        if seller_id:
            qs = qs.filter(seller_id=seller_id)

        shamsi_year = self.request.query_params.get('shamsi_year')
        if shamsi_year:
            qs = qs.filter(shamsi_year=shamsi_year)

        shamsi_month = self.request.query_params.get('shamsi_month')
        if shamsi_month:
            qs = qs.filter(shamsi_month=shamsi_month)

        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch=branch)

        # محدودسازی دسترسی در صورتی که ادمین/مدیرمالی نباشد
        if not (user.is_superuser or any(r.code in ['ADMIN', 'FINANCIAL_MANAGER'] for r in user.roles.all())):
            # اگر صندوق‌دار است، فقط شعبه خودش
            if any(r.code == 'CASHIER' for r in user.roles.all()):
                qs = qs.filter(branch=user.branch)
            elif any(r.code == 'SELLER_STAFF' for r in user.roles.all()):
                # فروشنده فقط فروش‌های خودش را می‌بیند
                qs = qs.filter(seller=user)
            else:
                # بالادستی زیردستان خودش را می‌بیند
                sub_ids = [u.id for u in user.get_all_subordinates()]
                qs = qs.filter(seller_id__in=sub_ids)

        return qs.order_by('shamsi_year', 'shamsi_month', 'shamsi_day')

    def perform_create(self, serializer):
        user = self.request.user
        seller = serializer.validated_data.get('seller')

        if not self._can_record_sales_for_seller(user, seller):
            raise PermissionDenied("شما مجاز به ثبت فروش برای این فروشنده نیستید (صندوق‌دار باید در همان شعبه باشد).")

        branch = seller.branch or user.branch or ''
        serializer.save(recorded_by=user, branch=branch)

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance

        if not self._can_record_sales_for_seller(user, instance.seller):
            raise PermissionDenied("شما مجاز به ویرایش فروش این فروشنده نیستید.")

        serializer.save(recorded_by=user)

    def perform_destroy(self, instance):
        user = self.request.user
        if not self._can_record_sales_for_seller(user, instance.seller):
            raise PermissionDenied("شما مجاز به حذف این رکورد نیستید.")
        instance.delete()

    @extend_schema(
        tags=['فروشندگان و پورسانت'],
        summary="ثبت تجمیعی (Bulk) فروش‌های روزانه کل ماه برای یک فروشنده",
        request=SellerDailySaleBulkSerializer,
    )
    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request):
        """
        ثبت یا به‌روزرسانی گروهی فروش روزهای ماه توسط صندوق‌دار.
        ورودی:
        {
            "seller": "<UUID>",
            "shamsi_year": 1403,
            "shamsi_month": 7,
            "daily_sales": [
                {"shamsi_day": 1, "amount": 10000000, "notes": ""},
                {"shamsi_day": 2, "amount": 12000000, "notes": ""}
            ]
        }
        """
        serializer = SellerDailySaleBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        seller = serializer.validated_data['seller']
        shamsi_year = serializer.validated_data['shamsi_year']
        shamsi_month = serializer.validated_data['shamsi_month']
        daily_sales = serializer.validated_data['daily_sales']

        if not self._can_record_sales_for_seller(user, seller):
            raise PermissionDenied("شما مجاز به ثبت فروش برای این فروشنده نیستید.")

        branch = seller.branch or user.branch or ''
        saved_records = []

        with transaction.atomic():
            for item in daily_sales:
                day = item['shamsi_day']
                amount = item['amount']
                notes = item.get('notes', '')

                record, _ = SellerDailySale.objects.update_or_create(
                    seller=seller,
                    shamsi_year=shamsi_year,
                    shamsi_month=shamsi_month,
                    shamsi_day=day,
                    defaults={
                        'amount': amount,
                        'notes': notes,
                        'recorded_by': user,
                        'branch': branch
                    }
                )
                saved_records.append(record)

        total_amount = sum(r.amount for r in saved_records)
        return Response({
            "message": f"تعداد {len(saved_records)} رکورد فروش با موفقیت ثبت/ویرایش شد.",
            "seller": str(seller.id),
            "shamsi_year": shamsi_year,
            "shamsi_month": shamsi_month,
            "total_sales_updated": float(total_amount),
            "records": SellerDailySaleSerializer(saved_records, many=True).data
        }, status=status.HTTP_200_OK)


# ── Liquidity Management Views (مدیریت نقدینگی) ───────────────────────────────

class IsLiquidityManager(permissions.BasePermission):
    """
    مجوز دسترسی به ماژول مدیریت نقدینگی:
    - ادمین کل و مدیر مالی: دسترسی کامل خواندن و نوشتن
    - مدیر اجرایی، سرپرست و حسابدار: دسترسی فقط خواندنی (GET)
    """
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True
        user_roles = {r.code for r in request.user.roles.all()}
        if 'ADMIN' in user_roles or 'FINANCIAL_MANAGER' in user_roles:
            return True
        if request.method in permissions.SAFE_METHODS:
            return bool(user_roles & {'EXECUTIVE_MANAGER', 'ACCOUNTANT', 'SUPERVISOR'})
        return False


@extend_schema(
    tags=['مدیریت نقدینگی - درآمد روزانه'],
)
class LiquidityDailyRevenueView(APIView):
    """
    دریافت و تنظیم میزان درآمد روزانه
    GET /api/liquidity/daily-revenue/
    POST/PUT /api/liquidity/daily-revenue/  {"amount": 50000000}
    """
    permission_classes = [IsLiquidityManager]

    @extend_schema(
        summary="دریافت تک‌مقدار درآمد روزانه فعلی کسب‌وکار",
        responses={200: LiquidityDailyRevenueSettingSerializer}
    )
    def get(self, request):
        setting = LiquidityDailyRevenueSetting.get_current_revenue()
        serializer = LiquidityDailyRevenueSettingSerializer(setting)
        return Response(serializer.data)

    @extend_schema(
        summary="تنظیم یا ویرایش میزان درآمد روزانه (POST)",
        request=LiquidityDailyRevenueSettingSerializer,
        responses={200: LiquidityDailyRevenueSettingSerializer}
    )
    def post(self, request):
        return self._update(request)

    @extend_schema(
        summary="تنظیم یا ویرایش میزان درآمد روزانه (PUT)",
        request=LiquidityDailyRevenueSettingSerializer,
        responses={200: LiquidityDailyRevenueSettingSerializer}
    )
    def put(self, request):
        return self._update(request)

    def _update(self, request):
        raw_amount = request.data.get('amount')
        if raw_amount is None:
            return Response({"error": "فیلد amount الزامی است."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = Decimal(str(raw_amount))
            if amount < 0:
                return Response({"error": "مبلغ درآمد روزانه نمی‌تواند منفی باشد."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"error": "مقدار مبلغ نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST)

        setting = LiquidityDailyRevenueSetting.get_current_revenue()
        setting.amount = amount
        setting.updated_by = request.user
        setting.save()

        serializer = LiquidityDailyRevenueSettingSerializer(setting)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ── Liquidity Daily Charges (شارژ روزانه نقدینگی) ──────────────────────────────

@extend_schema_view(
    list=extend_schema(
        tags=['مدیریت نقدینگی - شارژ روزانه'],
        summary="لیست شارژهای روزانه نقدینگی",
        description="دریافت لیست مبالغ شارژ شده روزانه نقدینگی به همراه تاریخ و ساعت دقیق ثبت",
        responses={200: LiquidityDailyChargeSerializer(many=True)},
        parameters=[
            OpenApiParameter('from_date', OpenApiTypes.DATE, description="فیلتر از تاریخ میلادی (YYYY-MM-DD)", required=False),
            OpenApiParameter('to_date', OpenApiTypes.DATE, description="فیلتر تا تاریخ میلادی (YYYY-MM-DD)", required=False),
        ]
    ),
    create=extend_schema(
        tags=['مدیریت نقدینگی - شارژ روزانه'],
        summary="ثبت شارژ روزانه نقدینگی جدید",
        description="ارسال مبلغ شارژ روزانه به سرور جهت ذخیره با تاریخ و ساعت جاری",
        request=LiquidityDailyChargeCreateSerializer,
        responses={201: LiquidityDailyChargeSerializer}
    ),
    retrieve=extend_schema(
        tags=['مدیریت نقدینگی - شارژ روزانه'],
        summary="مشاهده جزئیات یک شارژ روزانه",
        responses={200: LiquidityDailyChargeSerializer}
    ),
    destroy=extend_schema(
        tags=['مدیریت نقدینگی - شارژ روزانه'],
        summary="حذف رکورد شارژ روزانه",
        description="فقط ادمین و مدیر مالی مجاز به حذف شارژ روزانه هستند",
        responses={204: None}
    ),
)
class LiquidityDailyChargeViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsLiquidityManager]
    serializer_class = LiquidityDailyChargeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = LiquidityDailyCharge.objects.select_related('created_by').all()
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return LiquidityDailyChargeCreateSerializer
        return LiquidityDailyChargeSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        charge = serializer.save(created_by=request.user)
        output_serializer = LiquidityDailyChargeSerializer(charge, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)



@extend_schema_view(
    list=extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="لیست هزینه‌ها با فیلترهای تفکیکی و جستجو",
        parameters=[
            OpenApiParameter(
                name='scope', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                description="فیلتر نما/بازه: unpaid (پرداخت نشده - پیش‌فرض), paid (تسویه‌شده), next_week (سررسید ۷ روز آینده), overdue (معوق), this_month (ماه جاری شمسی), all (همه)",
                enum=['unpaid', 'paid', 'next_week', 'overdue', 'this_month', 'all']
            ),
            OpenApiParameter(
                name='status', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس وضعیت هوشمند محاسبه‌شده: EXCELLENT (عالی), NORMAL (عادی), WARNING (هشدار), CRITICAL (خطرناک), OVERDUE (عقب مانده), PAID (پرداخت شده)",
                enum=['EXCELLENT', 'NORMAL', 'WARNING', 'CRITICAL', 'OVERDUE', 'PAID']
            ),
            OpenApiParameter(
                name='category', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                description="دسته‌بندی هزینه: SUPPLIER (تامین‌کننده), SALARY (حقوق), RENT (اجاره), INSTALLMENTS (اقساط), OTHER_EXPENSES (سایر هزینه‌ها), MANAGEMENT (مدیریت), SAVINGS (پس‌انداز), CHARITY (خیریه), EQUIPMENT (تجهیزات)",
                enum=['SUPPLIER', 'SALARY', 'RENT', 'INSTALLMENTS', 'OTHER_EXPENSES', 'MANAGEMENT', 'SAVINGS', 'CHARITY', 'EQUIPMENT']
            ),
            OpenApiParameter(
                name='is_paid', type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY,
                description="فیلتر صریح وضعیت پرداخت (true یا false)"
            ),
            OpenApiParameter(
                name='search', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                description="جستجوی متنی در عنوان و توضیحات هزینه"
            ),
            OpenApiParameter(
                name='ordering', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                description="مرتب‌سازی: due_date, -due_date, amount, -amount, created_at, -created_at"
            ),
        ],
        responses={200: LiquidityExpenseListSerializer(many=True)}
    ),
    retrieve=extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="مشاهده جزئیات یک هزینه به همراه کلیه پرداخت‌های ثبت‌شده",
        responses={200: LiquidityExpenseSerializer}
    ),
    create=extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="ثبت هزینه تعهدشده جدید",
        request=LiquidityExpenseSerializer,
        responses={201: LiquidityExpenseSerializer}
    ),
    update=extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="ویرایش کامل هزینه",
        request=LiquidityExpenseSerializer,
        responses={200: LiquidityExpenseSerializer}
    ),
    partial_update=extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="ویرایش جزئی هزینه",
        request=LiquidityExpenseSerializer,
        responses={200: LiquidityExpenseSerializer}
    ),
    destroy=extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="حذف ایمن هزینه",
        responses={200: OpenApiTypes.OBJECT}
    ),
)
class LiquidityExpenseViewSet(SafeDestroyMixin, viewsets.ModelViewSet):
    """
    مدیریت هزینه‌های تعهد شده نقدینگی (CRUD، لیست با فیلترهای تفکیکی، ثبت پرداخت مرحله‌ای و تایید تسویه نهایی)
    """
    queryset = LiquidityExpense.objects.all()
    permission_classes = [IsLiquidityManager]
    serializer_class = LiquidityExpenseSerializer

    def get_serializer_class(self):
        if self.action == 'list':
            return LiquidityExpenseListSerializer
        return LiquidityExpenseSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        setting = LiquidityDailyRevenueSetting.get_current_revenue()
        ctx['daily_revenue'] = setting.amount
        return ctx

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return LiquidityExpense.objects.none()

        qs = LiquidityExpense.objects.select_related('created_by').prefetch_related('payments__created_by')

        if self.action != 'list':
            return qs

        # فیلتر جستجو
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))

        # فیلتر دسته‌بندی
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)

        # فیلتر وضعیت پرداخت صریح
        is_paid = self.request.query_params.get('is_paid')
        if is_paid is not None:
            if is_paid.lower() in ['true', '1']:
                qs = qs.filter(is_paid=True)
            elif is_paid.lower() in ['false', '0']:
                qs = qs.filter(is_paid=False)

        # فیلتر نماها / Scope
        scope = self.request.query_params.get('scope', 'unpaid')
        today = datetime.date.today()

        if scope == 'unpaid':
            qs = qs.filter(is_paid=False)
        elif scope == 'paid':
            qs = qs.filter(is_paid=True)
        elif scope == 'next_week':
            next_week = today + timedelta(days=7)
            qs = qs.filter(is_paid=False, due_date__gte=today, due_date__lte=next_week)
        elif scope == 'overdue':
            qs = qs.filter(is_paid=False, due_date__lt=today)
        elif scope == 'this_month':
            jy, jm, _ = get_current_shamsi()
            days_in_m = get_days_in_shamsi_month(jy, jm)
            start_g = get_gregorian_date(jy, jm, 1)
            end_g = get_gregorian_date(jy, jm, days_in_m)
            qs = qs.filter(is_paid=False, due_date__gte=start_g, due_date__lte=end_g)
        elif scope == 'all':
            pass  # بدون فیلتر پیش‌فرض

        # فیلتر بر اساس وضعیت هوشمند (status)
        status_param = self.request.query_params.get('status')
        if status_param:
            status_param = status_param.upper()
            daily_rev = LiquidityDailyRevenueSetting.get_current_revenue().amount
            all_candidates = list(qs)
            batch_metrics = LiquidityExpense.batch_calculate_metrics(all_candidates, daily_revenue=daily_rev)
            matching_ids = [
                exp.id for exp in all_candidates if batch_metrics.get(exp.id, {}).get('status') == status_param
            ]
            qs = qs.filter(id__in=matching_ids)

        # مرتب‌سازی
        ordering = self.request.query_params.get('ordering', 'due_date')
        if ordering in ['due_date', '-due_date', 'amount', '-amount', 'created_at', '-created_at']:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by('is_paid', 'due_date', '-created_at')

        return qs

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        items = list(page) if page is not None else list(queryset)

        # بهینه‌سازی: محاسبه تجمیعی متریک‌ها برای اقلام موجود در خروجی
        setting = LiquidityDailyRevenueSetting.get_current_revenue()
        batch_metrics = LiquidityExpense.batch_calculate_metrics(items, daily_revenue=setting.amount)

        ctx = self.get_serializer_context()
        ctx['batch_metrics'] = batch_metrics

        if page is not None:
            serializer = self.get_serializer(page, many=True, context=ctx)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(items, many=True, context=ctx)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="ثبت یک پرداخت مرحله‌ای / واریز ذخیره‌سازی به این هزینه",
        request=LiquidityExpensePaymentCreateSerializer,
        responses={201: LiquidityExpensePaymentCreateResponseSerializer}
    )
    @action(detail=True, methods=['post'], url_path='payments')
    def add_payment(self, request, pk=None):
        """
        ثبت یک پرداخت یا واریز ذخیره‌سازی به این هزینه
        POST /api/liquidity/expenses/{id}/payments/
        body: {"amount": 10000000, "date": "2026-09-22", "description": "واریز از صندوق"}
        """
        expense = self.get_object()
        raw_amount = request.data.get('amount')
        if not raw_amount:
            return Response({"error": "مبلغ پرداختی (amount) الزامی است."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = Decimal(str(raw_amount))
            if amount <= 0:
                return Response({"error": "مبلغ پرداختی باید بیشتر از صفر باشد."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"error": "فرمت مبلغ نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST)

        raw_date = request.data.get('date')
        if raw_date:
            if isinstance(raw_date, str):
                try:
                    pay_date = datetime.date.fromisoformat(raw_date)
                except Exception:
                    pay_date = datetime.date.today()
            else:
                pay_date = raw_date
        else:
            pay_date = datetime.date.today()

        description = request.data.get('description', '')

        payment = LiquidityExpensePayment.objects.create(
            expense=expense,
            amount=amount,
            date=pay_date,
            description=description,
            created_by=request.user
        )
        payment.refresh_from_db()

        expense.refresh_from_db()
        ctx = self.get_serializer_context()
        return Response({
            "message": "پرداخت با موفقیت ثبت شد.",
            "payment": LiquidityExpensePaymentSerializer(payment).data,
            "expense": LiquidityExpenseSerializer(expense, context=ctx).data
        }, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="حذف یک پرداخت مرحله‌ای ثبت‌شده",
        parameters=[
            OpenApiParameter(
                name='payment_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH,
                description="شناسه UUID پرداخت مرحله‌ای"
            )
        ],
        responses={200: LiquidityExpenseActionResponseSerializer}
    )
    @action(detail=True, methods=['delete'], url_path=r'payments/(?P<payment_id>[^/.]+)')
    def delete_payment(self, request, pk=None, payment_id=None):
        """
        حذف یک پرداخت مرحله‌ای ثبت‌شده
        DELETE /api/liquidity/expenses/{id}/payments/{payment_id}/
        """
        expense = self.get_object()
        try:
            payment = expense.payments.get(id=payment_id)
            payment.delete()
        except LiquidityExpensePayment.DoesNotExist:
            return Response({"error": "پرداخت مورد نظر یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        expense.refresh_from_db()
        ctx = self.get_serializer_context()
        return Response({
            "message": "پرداخت با موفقیت حذف شد.",
            "expense": LiquidityExpenseSerializer(expense, context=ctx).data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="تایید نهایی تسویه هزینه (خروج از کارت هزینه‌ها و ورود به پرداخت‌شده)",
        request=None,
        responses={200: LiquidityExpenseActionResponseSerializer}
    )
    @action(detail=True, methods=['post'], url_path='confirm-payment')
    def confirm_payment(self, request, pk=None):
        """
        تایید نهایی تسویه هزینه:
        1. بررسی عدم تایید قبلی
        2. بررسی موجودی کارت متناظر (قفل سخت‌گیرانه): در صورت کسری، خطای 400 بازمی‌گرداند.
        3. علامت‌گذاری is_paid = True
        4. کسر خودکار مبلغ از اعتبار کارت متناظر با ثبت تراکنش WITHDRAWAL
        POST /api/liquidity/expenses/{id}/confirm-payment/
        """
        expense = self.get_object()
        if expense.is_paid:
            return Response({"error": "این هزینه قبلاً تایید و تسویه شده است."}, status=status.HTTP_400_BAD_REQUEST)

        # محاسبه موجودی فعلی کارت این دسته‌بندی
        card_type = expense.category
        tx_qs = LiquidityCardTransaction.objects.filter(card_type=card_type)
        deposits = tx_qs.filter(transaction_type='DEPOSIT').aggregate(s=models.Sum('amount'))['s'] or Decimal('0.00')
        withdrawals = tx_qs.filter(transaction_type='WITHDRAWAL').aggregate(s=models.Sum('amount'))['s'] or Decimal('0.00')
        card_balance = deposits - withdrawals

        card_title = dict(LiquidityCardTransaction.CARD_TYPE_CHOICES).get(card_type, card_type)

        # قفل سخت‌گیرانه در صورت ناکافی بودن موجودی کارت
        if card_balance < expense.amount:
            return Response({
                "error": f"موجودی {card_title} ({float(card_balance):,.0f} تومان) برای پرداخت این هزینه ({float(expense.amount):,.0f} تومان) کافی نیست. ابتدا کارت را شارژ کنید."
            }, status=status.HTTP_400_BAD_REQUEST)

        expense.is_paid = True
        expense.paid_at = timezone.now()
        expense.save()

        # ثبت خودکار تراکنش برداشت از کارت متناظر
        LiquidityCardTransaction.objects.create(
            card_type=card_type,
            transaction_type='WITHDRAWAL',
            amount=expense.amount,
            date=datetime.date.today(),
            description=f"تسویه و پرداخت هزینه: {expense.title}",
            expense=expense,
            created_by=request.user
        )

        ctx = self.get_serializer_context()
        return Response({
            "message": "هزینه با موفقیت پرداخت شد و از اعتبار کارت کسر گردید.",
            "expense": LiquidityExpenseSerializer(expense, context=ctx).data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="بازگردانی وضعیت هزینه از تسویه‌شده به جاری/فعال (بازگشت اعتبار به کارت)",
        request=None,
        responses={200: LiquidityExpenseActionResponseSerializer}
    )
    @action(detail=True, methods=['post'], url_path='unconfirm-payment')
    def unconfirm_payment(self, request, pk=None):
        """
        بازگردانی وضعیت هزینه از پرداخت‌شده به پرداخت‌نشده:
        ابطال تراکنش کسر از کارت و بازگردانی اعتبار به کارت
        POST /api/liquidity/expenses/{id}/unconfirm-payment/
        """
        expense = self.get_object()
        if not expense.is_paid:
            return Response({"error": "این هزینه پرداخت نشده است."}, status=status.HTTP_400_BAD_REQUEST)

        expense.is_paid = False
        expense.paid_at = None
        expense.save()

        # حذف تراکنش‌های کسر مرتبط با این هزینه
        expense.card_transactions.filter(transaction_type='WITHDRAWAL').delete()

        ctx = self.get_serializer_context()
        return Response({
            "message": "وضعیت پرداخت هزینه با موفقیت بازگردانی شد و مبلغ به کارت بازگشت.",
            "expense": LiquidityExpenseSerializer(expense, context=ctx).data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['مدیریت نقدینگی - هزینه‌ها'],
        summary="خلاصه شمارنده‌ها، وضعیت‌ها و مبالغ برای تب‌های فرانت‌اند",
        responses={200: LiquidityExpenseSummaryResponseSerializer}
    )
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        خلاصه شمارنده‌ها و مبالغ برای تب‌ها و نشان‌های فرانت‌اند
        GET /api/liquidity/expenses/summary/
        """
        today = datetime.date.today()
        next_week = today + timedelta(days=7)
        daily_rev = LiquidityDailyRevenueSetting.get_current_revenue().amount

        all_expenses = list(LiquidityExpense.objects.prefetch_related('payments').all())
        unpaid = [e for e in all_expenses if not e.is_paid]
        paid = [e for e in all_expenses if e.is_paid]

        next_week_items = [e for e in unpaid if today <= e.due_date <= next_week]
        overdue_items = [e for e in unpaid if e.due_date < today]

        # وضعیت‌ها بر اساس فرمول نقدینگی جدید
        status_counts = {'EXCELLENT': 0, 'NORMAL': 0, 'WARNING': 0, 'CRITICAL': 0, 'OVERDUE': 0, 'PAID': len(paid)}
        batch_metrics = LiquidityExpense.batch_calculate_metrics(unpaid, daily_revenue=daily_rev)
        for e in unpaid:
            st = batch_metrics.get(e.id, {}).get('status')
            if st in status_counts:
                status_counts[st] += 1

        total_unpaid_amount = sum(e.amount for e in unpaid)
        total_allocated_amount = sum(e.allocated_amount for e in unpaid)
        total_remaining_amount = max(Decimal('0.00'), total_unpaid_amount - total_allocated_amount)

        return Response({
            "total_count": len(all_expenses),
            "unpaid_count": len(unpaid),
            "paid_count": len(paid),
            "next_week_count": len(next_week_items),
            "overdue_count": len(overdue_items),
            "critical_count": status_counts['CRITICAL'],
            "warning_count": status_counts['WARNING'],
            "normal_count": status_counts['NORMAL'],
            "excellent_count": status_counts['EXCELLENT'],
            "total_unpaid_amount": float(total_unpaid_amount),
            "total_allocated_amount": float(total_allocated_amount),
            "total_remaining_amount": float(total_remaining_amount),
        }, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        tags=['مدیریت نقدینگی - کارت‌ها'],
        summary="نمای کلی وضعیت هر ۹ کارت نقدینگی (هزینه‌ها، موجودی، واریز و برداشت)",
        responses={200: LiquidityCardsOverviewSerializer}
    )
)
class LiquidityCardsViewSet(viewsets.ViewSet):
    """
    مدیریت کارت‌های ۹‌گانه نقدینگی:
    تامین کننده، حقوق، اجاره، اقساط، سایر هزینه ها، مدیریت، پس انداز، خیریه، تجهیزات
    شامل: موجودی، واریزها، برداشت‌ها، و مجموع هزینه‌های پرداخت‌نشده تا ۳۰ روز آینده.
    """
    permission_classes = [IsLiquidityManager]

    def _normalize_card_type(self, raw_code):
        if not raw_code:
            return None
        normalized = str(raw_code).upper().replace('-', '_')
        valid_codes = [c[0] for c in LiquidityCardTransaction.CARD_TYPE_CHOICES]
        if normalized in valid_codes:
            return normalized
        return None

    def _get_card_data(self, card_code, card_title):
        today = datetime.date.today()
        month_limit = today + datetime.timedelta(days=30)

        tx_qs = LiquidityCardTransaction.objects.filter(card_type=card_code)
        deposits = tx_qs.filter(transaction_type='DEPOSIT').aggregate(s=models.Sum('amount'))['s'] or Decimal('0.00')
        withdrawals = tx_qs.filter(transaction_type='WITHDRAWAL').aggregate(s=models.Sum('amount'))['s'] or Decimal('0.00')
        balance = deposits - withdrawals

        # هزینه‌های پرداخت نشده تا ۳۰ روز آینده (شامل معوقه‌ها)
        expenses_qs = LiquidityExpense.objects.filter(
            category=card_code,
            is_paid=False,
            due_date__lte=month_limit
        )
        total_expenses = expenses_qs.aggregate(s=models.Sum('amount'))['s'] or Decimal('0.00')
        expenses_count = expenses_qs.count()

        recent_tx = LiquidityCardTransactionSerializer(
            tx_qs.order_by('-date', '-created_at')[:5], many=True
        ).data

        return {
            "card_type": card_code,
            "title": card_title,
            "balance": float(balance),
            "total_deposits": float(deposits),
            "total_withdrawals": float(withdrawals),
            "total_expenses": float(total_expenses),
            "expenses_count": expenses_count,
            "recent_transactions": recent_tx
        }

    def list(self, request):
        return self.overview(request)

    @extend_schema(
        tags=['مدیریت نقدینگی - کارت‌ها'],
        summary="خلاصه لحظه‌ای وضعیت هر ۹ کارت نقدینگی",
        responses={200: LiquidityCardsOverviewSerializer}
    )
    @action(detail=False, methods=['get'], url_path='overview')
    def overview(self, request):
        cards_list = []
        cards_by_type = {}
        total_balance = Decimal('0.00')
        total_upcoming_expenses = Decimal('0.00')
        total_all_deposits = Decimal('0.00')
        total_all_withdrawals = Decimal('0.00')

        for code, title in LiquidityCardTransaction.CARD_TYPE_CHOICES:
            card_info = self._get_card_data(code, title)
            cards_list.append(card_info)
            cards_by_type[code.lower()] = card_info
            total_balance += Decimal(str(card_info['balance']))
            total_upcoming_expenses += Decimal(str(card_info['total_expenses']))
            total_all_deposits += Decimal(str(card_info['total_deposits']))
            total_all_withdrawals += Decimal(str(card_info['total_withdrawals']))

        return Response({
            "summary": {
                "total_balance": float(total_balance),
                "total_expenses": float(total_upcoming_expenses),
                "total_deposits": float(total_all_deposits),
                "total_withdrawals": float(total_all_withdrawals),
            },
            "cards": cards_list,
            "cards_by_type": cards_by_type
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['مدیریت نقدینگی - کارت‌ها'],
        summary="جزئیات و تاریخچه تراکنش‌های یک کارت نقدینگی",
        parameters=[
            OpenApiParameter(
                name='id', type=OpenApiTypes.STR, location=OpenApiParameter.PATH,
                description="کد نوع کارت نقدینگی (مانند: supplier, salary, rent, installments, other_expenses, management, savings, charity, equipment)"
            ),
            OpenApiParameter(
                name='type', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس نوع تراکنش: DEPOSIT (واریز) یا WITHDRAWAL (برداشت)",
                enum=['DEPOSIT', 'WITHDRAWAL']
            )
        ],
        responses={200: LiquidityCardDetailResponseSerializer}
    )
    def retrieve(self, request, pk=None):
        """
        دریافت اطلاعات و تراکنش‌های یک کارت:
        GET /api/liquidity/cards/{card_type}/
        (مثلاً: salary, rent, supplier, installments, other_expenses, management, savings, charity, equipment)
        """
        card_code = self._normalize_card_type(pk)
        if not card_code:
            valid_list = [c[0] for c in LiquidityCardTransaction.CARD_TYPE_CHOICES]
            return Response({
                "error": f"کارت نامعتبر است. کارت‌های معتبر: {', '.join(valid_list)}"
            }, status=status.HTTP_404_NOT_FOUND)

        card_title = dict(LiquidityCardTransaction.CARD_TYPE_CHOICES).get(card_code, card_code)
        card_data = self._get_card_data(card_code, card_title)

        qs = LiquidityCardTransaction.objects.filter(card_type=card_code).select_related('created_by', 'expense')
        tx_type = request.query_params.get('type')
        if tx_type:
            qs = qs.filter(transaction_type=tx_type.upper())

        transactions = LiquidityCardTransactionSerializer(qs.order_by('-date', '-created_at'), many=True).data

        return Response({
            "card_type": card_code,
            "title": card_title,
            "balance": card_data['balance'],
            "total_deposits": card_data['total_deposits'],
            "total_withdrawals": card_data['total_withdrawals'],
            "total_expenses": card_data['total_expenses'],
            "expenses_count": card_data['expenses_count'],
            "transactions": transactions
        }, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="liquidity_card_specific_transaction_create",
        tags=['مدیریت نقدینگی - کارت‌ها'],
        summary="ثبت تراکنش واریز یا برداشت برای کارت مشخص",
        parameters=[
            OpenApiParameter(
                name='id', type=OpenApiTypes.STR, location=OpenApiParameter.PATH,
                description="کد نوع کارت نقدینگی (مانند: supplier, salary, rent, installments, other_expenses, management, savings, charity, equipment)"
            )
        ],
        request=LiquidityCardTransactionCreateSerializer,
        responses={201: LiquidityCardTransactionCreateResponseSerializer}
    )
    @action(detail=True, methods=['post'], url_path='transactions')
    def add_card_transaction(self, request, pk=None):
        """
        ثبت تراکنش واریز یا برداشت برای یک کارت:
        POST /api/liquidity/cards/{card_type}/transactions/
        """
        card_code = self._normalize_card_type(pk)
        if not card_code:
            valid_list = [c[0] for c in LiquidityCardTransaction.CARD_TYPE_CHOICES]
            return Response({
                "error": f"کارت نامعتبر است. کارت‌های معتبر: {', '.join(valid_list)}"
            }, status=status.HTTP_404_NOT_FOUND)

        return self._add_card_transaction(request, card_code)

    @extend_schema(
        operation_id="liquidity_cards_general_transaction_create",
        tags=['مدیریت نقدینگی - کارت‌ها'],
        summary="ثبت تراکنش عمومی در کارت‌های نقدینگی با تعیین نوع کارت در بدنه",
        request=LiquidityCardTransactionCreateSerializer,
        responses={201: LiquidityCardTransactionCreateResponseSerializer}
    )
    @action(detail=False, methods=['post'], url_path='transactions')
    def add_general_transaction(self, request):
        """
        ثبت تراکنش واریز یا برداشت کارت با ارسال card_type در بدنه:
        POST /api/liquidity/cards/transactions/
        """
        raw_card = request.data.get('card_type')
        if not raw_card:
            return Response({"error": "فیلد card_type الزامی است."}, status=status.HTTP_400_BAD_REQUEST)
        card_code = self._normalize_card_type(raw_card)
        if not card_code:
            valid_list = [c[0] for c in LiquidityCardTransaction.CARD_TYPE_CHOICES]
            return Response({
                "error": f"نوع کارت نامعتبر است. کارت‌های معتبر: {', '.join(valid_list)}"
            }, status=status.HTTP_400_BAD_REQUEST)

        return self._add_card_transaction(request, card_code)

    @extend_schema(
        tags=['مدیریت نقدینگی - کارت‌ها'],
        summary="حذف یک تراکنش از کارت‌های نقدینگی",
        parameters=[
            OpenApiParameter(
                name='tx_id', type=OpenApiTypes.UUID, location=OpenApiParameter.PATH,
                description="شناسه UUID تراکنش کارت"
            )
        ],
        responses={200: LiquiditySimpleMessageResponseSerializer}
    )
    @action(detail=False, methods=['delete'], url_path=r'transactions/(?P<tx_id>[^/.]+)')
    def delete_transaction(self, request, tx_id=None):
        """
        حذف یک تراکنش از کارت‌های نقدینگی
        DELETE /api/liquidity/cards/transactions/{tx_id}/
        """
        try:
            tx = LiquidityCardTransaction.objects.get(id=tx_id)
            tx.delete()
            return Response({"message": "تراکنش با موفقیت حذف شد."}, status=status.HTTP_200_OK)
        except LiquidityCardTransaction.DoesNotExist:
            return Response({"error": "تراکنش یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

    def _add_card_transaction(self, request, card_type):
        raw_amount = request.data.get('amount')
        tx_type = request.data.get('transaction_type')
        if not raw_amount or not tx_type:
            return Response({"error": "فیلدهای amount و transaction_type الزامی هستند."}, status=status.HTTP_400_BAD_REQUEST)

        tx_type = tx_type.upper()
        if tx_type not in ['DEPOSIT', 'WITHDRAWAL']:
            return Response({"error": "نوع تراکنش باید DEPOSIT یا WITHDRAWAL باشد."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(raw_amount))
            if amount <= 0:
                return Response({"error": "مبلغ باید بزرگتر از صفر باشد."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"error": "مبلغ نامعتبر است."}, status=status.HTTP_400_BAD_REQUEST)

        raw_date = request.data.get('date')
        if raw_date:
            if isinstance(raw_date, str):
                try:
                    tx_date = datetime.date.fromisoformat(raw_date)
                except Exception:
                    tx_date = datetime.date.today()
            else:
                tx_date = raw_date
        else:
            tx_date = datetime.date.today()

        description = request.data.get('description', '')

        tx = LiquidityCardTransaction.objects.create(
            card_type=card_type,
            transaction_type=tx_type,
            amount=amount,
            date=tx_date,
            description=description,
            created_by=request.user
        )
        tx.refresh_from_db()

        return Response({
            "message": "تراکنش با موفقیت ثبت شد.",
            "transaction": LiquidityCardTransactionSerializer(tx).data
        }, status=status.HTTP_201_CREATED)
