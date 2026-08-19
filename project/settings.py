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
    'DESCRIPTION': 'سیستم مدیریت خرده‌فروشی RetailHub',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,

    # رفع warning: UUID path parameters
    'SCHEMA_PATH_PREFIX': r'/api/',

    # رفع warning: enum naming collision برای فیلدهای status و frequency
    'ENUM_NAME_OVERRIDES': {
        'ChecklistFrequencyEnum': 'core.models.Checklist.FREQUENCY_CHOICES',
        'MissionStatusEnum':      'core.models.Mission.STATUS_CHOICES',
        'DepositOrderStatusEnum': 'core.models.DepositOrder.STATUS_CHOICES',
        'ClaimStatusEnum':        'core.models.Claim.STATUS_CHOICES',
        'ReturnRequestStatusEnum':'core.models.ReturnRequest.STATUS_CHOICES',
    },

    # رفع warning: type hint برای get_superiors_info
    'COMPONENT_SPLIT_REQUEST': True,
}