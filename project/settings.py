# -*- coding: utf-8 -*-
import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-key-for-saas-paas-vps-portability-2026')
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'core',
    'drf_spectacular',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}

AUTH_USER_MODEL = 'core.CustomUser'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.CustomStatelessAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ✅ باگ ۷ رفع شد:
# قانون مرورگر: نمی‌توان همزمان ALLOW_ALL_ORIGINS=True و ALLOW_CREDENTIALS=True داشت.
# اگر فرانت‌اند شما نیازی به ارسال کوکی یا هدر خاص ندارد (که ندارد، چون از Bearer Token استفاده می‌کند)،
# CREDENTIALS را False می‌گذاریم تا با ALLOW_ALL_ORIGINS سازگار باشد.
CORS_ALLOW_ALL_ORIGINS  = True   # همه origin ها مجازند
CORS_ALLOW_CREDENTIALS = False   # کوکی ارسال نمی‌شود (Bearer Token جایگزین است)

# اگر در آینده خواستید به دامنه‌های خاص محدود کنید، این دو خط را جایگزین بالایی‌ها کنید:
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:3000",
#     "https://your-frontend-domain.com",
# ]

LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── تنظیمات drf-spectacular ──────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'RetailHub API',
    'DESCRIPTION': 'مستندات تعاملی وب‌سرویس جامع مدیریت خرده‌فروشی و نقدینگی RetailHub (نسخه ۲.۰)',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,

    # رفع warning: UUID path parameters
    'SCHEMA_PATH_PREFIX': r'/api/',

    # رفع warning: enum naming collision برای فیلدهای status و frequency
    'ENUM_NAME_OVERRIDES': {
        'ChecklistFrequencyEnum':    'core.models.Checklist.FREQUENCY_CHOICES',
        'MissionStatusEnum':         'core.models.Mission.STATUS_CHOICES',
        'DepositOrderStatusEnum':    'core.models.DepositOrder.STATUS_CHOICES',
        'ClaimStatusEnum':           'core.models.Claim.STATUS_CHOICES',
        'ReturnRequestStatusEnum':   'core.models.ReturnRequest.STATUS_CHOICES',
        'BranchTransferStatusEnum':  'core.models.BranchTransfer.STATUS_CHOICES',
        'WasteReportStatusEnum':     'core.models.WasteReport.STATUS_CHOICES',
        'AdvanceRequestStatusEnum':  'core.models.AdvanceRequest.STATUS_CHOICES',
        'BranchChoiceEnum':          'core.models.BRANCH_CHOICES',
        'LiquidityExpenseStatusEnum':'core.models.LiquidityExpense.EXPENSE_STATUS_CHOICES',
    },

    # دسته‌بندی موضوعی فارسی در سایدبار Swagger و ReDoc
    'TAGS': [
        {'name': 'احراز هویت و دسترسی', 'description': 'ورود به سیستم و دریافت توکن دسترسی بدون‌حالت (Stateless JWT)'},
        {'name': 'مدیریت کاربران', 'description': 'مدیریت کاربران، نقش‌ها، حذف هوشمند (کامل/نرم)، بازیابی حساب، و ساختار سلسله‌مراتبی'},
        {'name': 'شعب', 'description': 'لیست شعب معتبر و تغییر شعبه فعال کاربران'},
        {'name': 'مدیریت نقدینگی - کارت‌ها', 'description': 'مدیریت ۹ کارت اختصاصی (تامین‌کننده، حقوق، اجاره، اقساط، سایر هزینه‌ها، مدیریت، پس‌انداز، خیریه، تجهیزات)، موجودی و تراکنش‌ها'},
        {'name': 'مدیریت نقدینگی - هزینه‌ها', 'description': 'ثبت، لیست، فیلترهای هوشمند، تسویه نهایی با کسر خودکار از کارت، و پرداخت‌های مرحله‌ای'},
        {'name': 'مدیریت نقدینگی - درآمد روزانه', 'description': 'تنظیم و دریافت تک‌مقدار درآمد روزانه کسب‌وکار جهت فرمول‌های محاسباتی'},
        {'name': 'مدیریت نقدینگی - شارژ روزانه', 'description': 'ثبت و مشاهده لیست مبالغ شارژ شده روزانه نقدینگی به همراه تاریخ و ساعت'},
        {'name': 'فروش و فاکتورها', 'description': 'ثبت و مدیریت فاکتورهای فروش، تسویه‌های نقدی، پوز، چکی و اتصال به بیعانه'},
        {'name': 'فروشندگان و پورسانت', 'description': 'تعریف مدل‌های پورسانت، ثبت فروش‌های روزانه و استعلام جامع ماهانه فروشنده'},
        {'name': 'مشتریان', 'description': 'مدیریت بانک اطلاعاتی مشتریان، سوابق خرید و جستجو'},
        {'name': 'هزینه‌های عمومی', 'description': 'ثبت و مدیریت هزینه‌های عمومی فروشگاه، چک‌های صادره و تنخواه'},
        {'name': 'چک‌لیست‌ها و وظایف', 'description': 'مدیریت و نظارت بر انجام وظایف و چک‌لیست‌های روزانه، هفتگی و ماهانه پرسنل'},
        {'name': 'ماموریت‌ها', 'description': 'تعریف، تخصیص و پیگیری وضعیت ماموریت‌های اداری و عملیاتی پرسنل'},
        {'name': 'گزارش‌های دوره‌ای و مهلت‌دار', 'description': 'تعریف الگوهای گزارش‌دهی و ارسال گزارش‌های متنی و تصویری کارکنان'},
        {'name': 'مساعده کارکنان', 'description': 'فرآیند ثبت و تایید چندمرحله‌ای (سرپرست، ادمین، مدیر مالی) درخواست‌های مساعده'},
        {'name': 'خسارت و ضایعات', 'description': 'ثبت خسارت‌ها و گزارش ضایعات اقلام و تاییدیه انباردار'},
        {'name': 'مطالبات و پیگیری‌ها', 'description': 'ثبت مطالبات معوق، ثبت پیگیری‌ها و تعیین وضعیت تسویه'},
        {'name': 'برگشتی کالا و وجه', 'description': 'درخواست‌های مرجوعی کالا، عودت وجه یا تعویض جنس'},
        {'name': 'حواله و انتقال بین شعب', 'description': 'انتقال کالا بین شعب فروشگاه با تایید مبدا و مقصد'},
        {'name': 'سفارش‌های بیعانه', 'description': 'مدیریت سفارش‌های همراه با بیعانه و تسویه در فاکتور نهایی'},
        {'name': 'انبار و خروج کالا', 'description': 'ثبت و پیگیری خروج کالاهای امانی، نمونه و اداری از فروشگاه'},
        {'name': 'مدیریت فایل‌ها و رسانه', 'description': 'سرویس آپلود تصاویر، اسناد، فاکتورها و مدارک با فرمت‌های مجاز'},
    ],

    'COMPONENT_SPLIT_REQUEST': True,

    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
        'filter': True,
        'docExpansion': 'none',
        'displayRequestDuration': True,
        'defaultModelsExpandDepth': 1,
    },
    'REDOC_UI_SETTINGS': {
        'expandResponses': 'all',
    },
}
