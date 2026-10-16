# 📋 مستندات جامع API — سیستم درخواست کارکنان (Employee Requests)

> **نسخه:** ۱.۰ (RetailHub v21)  
> **مسیر ریشه API:** `/api/employee-requests/`  
> **احراز هویت:** `Authorization: Bearer <access_token>` (Stateless Token)

---

## 🌟 ۱. نمای کلی سیستم (Overview)

سیستم درخواست کارکنان جهت مدیریت و گردش‌کار انواع درخواست‌های پرسنلی در مجموعه توسعه داده شده است. این سیستم از گردش کار تأیید چندمرحله‌ای (مشابه ثبت انتقالی کالا بین شعب) بهره می‌برد و شامل لاگ کامل تاریخچه مراحل، امکان لغو توسط کارمند، و یکپارچه‌سازی با حسابداری و مدیر مالی می‌باشد.

### انواع ۴ گانه درخواست‌ها:
1. **مرخصی (`LEAVE`):** در دو مدل **روزانه** (`DAILY` با مشخص کردن لیست تاریخ‌ها) یا **ساعتی** (`HOURLY` با مشخص کردن روز و ساعت شروع/پایان).
2. **مساعده (`ADVANCE`):** درخواست مبلغ پیش‌دریافت حقوق با فیلد `advance_amount`؛ در مرحله مالی نیاز به ثبت تاریخ پرداخت (`payment_date`) داشته و وضعیت نهایی آن به جای تایید عادی به **پرداخت شده** (`PAID`) تبدیل می‌شود.
3. **اضافه‌کاری (`OVERTIME`):** ثبت تاریخ و ساعت شروع و پایان اضافه‌کاری انجام‌شده.
4. **متفرقه (`MISC`):** درخواست‌های اختصاصی، دورکاری، تجهیزات یا سایر امور با عنوان مشخص (`misc_title`) و توضیحات.

---

## 🔄 ۲. نمودار جریان تأیید مراحل (Approval Flow)

```
[ثبت درخواست توسط کارمند]
           │
           ▼
[در انتظار تایید بالادستی (PENDING_SUPERIOR)]
   ├── [لغو توسط کارمند (CANCELLED)] (فقط قبل از تایید بالادستی)
   ├── [رد توسط بالادستی (REJECTED_BY_SUPERIOR)]
   └── [تایید بالادستی]
           │
           ├─► اگر بالادستی ادمین باشد (ادغام مرحله) ─────────────┐
           │                                                     │
           ▼                                                     │
[در انتظار تایید ادمین (PENDING_ADMIN)]                          │
   ├── [رد توسط ادمین (REJECTED_BY_ADMIN)]                        │
   └── [تایید ادمین]                                             │
           │                                                     │
           ▼                                                     │
[در انتظار تایید مدیر مالی (PENDING_FINANCE)] ◄─────────────────┘
   ├── [رد توسط مدیر مالی (REJECTED_BY_FINANCE)]
   └── [تایید مدیر مالی]
           │
           ├── اگر نوع درخواست مساعده (ADVANCE) باشد ──► [پرداخت شده (PAID) + ثبت تاریخ پرداخت]
           └── برای سایر انواع (LEAVE, OVERTIME, MISC) ──► [تایید نهایی (APPROVED)]
```

### 💡 قوانین کلیدی گردش کار:
* **انتخاب بالادستی:** اگر کارمند در سیستم دارای چند بالادستی باشد، ارسال فیلد `superior_id` اجباری است تا کارمند مشخص کند درخواست به کدام بالادست ارجاع شود. اگر کارمند فقط یک بالادست داشته باشد، سیستم به صورت خودکار همان کاربر را به عنوان بالادست انتخاب می‌کند.
* **ادغام تأیید بالادستی و ادمین:** اگر بالادستی انتخاب‌شده دارای نقش `ADMIN` یا دسترسی Superuser باشد، مرحله ادمین به صورت خودکار تجمیع شده (Skip می‌شود) و مستقیماً پس از تایید بالادستی، درخواست به کارتابل مدیر مالی (`PENDING_FINANCE`) منتقل می‌شود.
* **ثبت لاگ وقایع (Stage Logging):** در هر مرحله از چرخه، یک رکورد در جدول `EmployeeRequestLog` به همراه کاربر انجام‌دهنده، مرحله مربوطه (`SUBMIT`, `SUPERIOR`, `ADMIN`, `FINANCE`, `CANCEL`)، تاریخ و زمان، و متن توضیحات به صورت خودکار درج می‌گردد.
* **قانون لغو (Cancel):** کارمند صرفاً می‌تواند درخواست‌های خود را که در وضعیت `PENDING_SUPERIOR` هستند لغو کند. پس از بررسی یا تایید بالادستی، امکان لغو توسط کاربر وجود ندارد.

---

## 📑 ۳. جدول خلاصه Endpointها

| متد | آدرس Endpoint | شرح عملکرد | دسترسی و شروط |
|---|---|---|---|
| `GET` | `/api/employee-requests/` | لیست درخواست‌های من و زیردستان | 🔐 کلیه کاربران لاگین‌شده |
| `POST` | `/api/employee-requests/` | ثبت درخواست جدید | 🔐 کلیه کاربران لاگین‌شده |
| `GET` | `/api/employee-requests/{id}/` | مشاهده جزئیات کامل درخواست + لاگ‌ها | 🔐 صاحب رکورد، بالادست یا ادمین |
| `POST` | `/api/employee-requests/{id}/cancel/` | لغو درخواست توسط کارمند | 🔐 فقط ثبت‌کننده (قبل از بررسی) |
| `POST` | `/api/employee-requests/{id}/superior-review/` | تایید یا رد توسط بالادستی | 👑 بالادستی ارجاع‌شده یا ادمین |
| `POST` | `/api/employee-requests/{id}/admin-review/` | تایید یا رد توسط ادمین | 👑 فقط ادمین یا سوپریوزر |
| `POST` | `/api/employee-requests/{id}/finance-review/` | تایید/پرداخت نهایی توسط مدیر مالی | 💰 مدیر مالی یا ادمین |
| `GET` | `/api/employee-requests/my-inbox/` | کارتابل بالادستی (ارجاع‌شده به من) | 🔐 بالادستان (فیلتر بر اساس کاربر جاری) |
| `GET` | `/api/employee-requests/admin-list/` | فهرست جامع کلیه درخواست‌ها | 👑 ادمین و مدیر مالی |

---

## 🔍 ۴. شرح دقیق Endpointها و نمونه Payloadها

### ۱. ثبت درخواست جدید (`POST /api/employee-requests/`)

#### فیلدهای مشترک:
* `request_type` *(اجباری)*: یکی از مقادیر `LEAVE`, `ADVANCE`, `OVERTIME`, `MISC`
* `description` *(اختیاری)*: توضیحات تکمیلی
* `superior_id` *(در صورت داشتن چند بالادستی اجباری)*: شناسه عددی بالادستی انتخاب‌شده

---

#### الف) درخواست مرخصی روزانه (`LEAVE` - `DAILY`)
```json
POST /api/employee-requests/
Content-Type: application/json

{
  "request_type": "LEAVE",
  "leave_mode": "DAILY",
  "leave_days": ["2026-11-01", "2026-11-02"],
  "superior_id": 14,
  "description": "مرخصی استحقاقی جهت امور شخصی"
}
```

#### ب) درخواست مرخصی ساعتی (`LEAVE` - `HOURLY`)
```json
POST /api/employee-requests/
Content-Type: application/json

{
  "request_type": "LEAVE",
  "leave_mode": "HOURLY",
  "leave_day": "2026-11-05",
  "leave_start_time": "10:00:00",
  "leave_end_time": "13:30:00",
  "superior_id": 14,
  "description": "مراجعه به اداره بیمه"
}
```

#### ج) درخواست مساعده (`ADVANCE`)
```json
POST /api/employee-requests/
Content-Type: application/json

{
  "request_type": "ADVANCE",
  "advance_amount": "5000000.00",
  "superior_id": 14,
  "description": "درخواست مساعده حقوق آبان ماه"
}
```

#### د) درخواست اضافه‌کاری (`OVERTIME`)
```json
POST /api/employee-requests/
Content-Type: application/json

{
  "request_type": "OVERTIME",
  "overtime_day": "2026-11-08",
  "overtime_start": "18:00:00",
  "overtime_end": "21:30:00",
  "superior_id": 14,
  "description": "حضور در انبارگردانی پایان فصل"
}
```

#### ه) درخواست متفرقه (`MISC`)
```json
POST /api/employee-requests/
Content-Type: application/json

{
  "request_type": "MISC",
  "misc_title": "درخواست دورکاری موقت",
  "superior_id": 14,
  "description": "به دلیل خرابی سیستم شعبه درخواست فعالیت دورکاری دارم."
}
```

#### پاسخ موفق ایجاد (HTTP 201 Created):
```json
{
  "id": "e44d33a1-7788-4444-9999-abcdef012345",
  "requester": 25,
  "requester_name": "علی محمدی",
  "request_type": "LEAVE",
  "request_type_display": "مرخصی",
  "description": "مرخصی استحقاقی جهت امور شخصی",
  "status": "PENDING_SUPERIOR",
  "status_display": "در انتظار تایید بالادستی",
  "target_superior": 14,
  "target_superior_name": "حسن رضایی",
  "leave_mode": "DAILY",
  "leave_mode_display": "روزانه",
  "leave_days": ["2026-11-01", "2026-11-02"],
  "leave_day": null,
  "leave_start_time": null,
  "leave_end_time": null,
  "advance_amount": null,
  "overtime_day": null,
  "overtime_start": null,
  "overtime_end": null,
  "misc_title": null,
  "superior_reviewer": null,
  "superior_reviewer_name": null,
  "superior_note": null,
  "superior_reviewed_at": null,
  "admin_reviewer": null,
  "admin_reviewer_name": null,
  "admin_note": null,
  "admin_reviewed_at": null,
  "finance_reviewer": null,
  "finance_reviewer_name": null,
  "finance_note": null,
  "finance_reviewed_at": null,
  "payment_date": null,
  "logs": [
    {
      "id": "11112222-3333-4444-5555-666677778888",
      "stage": "SUBMIT",
      "stage_display": "ثبت درخواست",
      "actor_name": "علی محمدی",
      "actor_username": "alimohammadi",
      "action": "درخواست مرخصی ثبت شد و به بالادستی (حسن رضایی) ارجاع داده شد.",
      "created_at": "2026-10-16T19:30:00Z"
    }
  ],
  "created_at": "2026-10-16T19:30:00Z",
  "updated_at": "2026-10-16T19:30:00Z"
}
```

---

### ۲. لغو درخواست توسط کارمند (`POST /api/employee-requests/{id}/cancel/`)

این متد نیازی به بدنه (body) ندارد. فقط درخواست‌کننده در صورتی که هنوز وضعیت `PENDING_SUPERIOR` باشد می‌تواند آن را صدا بزند.

```http
POST /api/employee-requests/e44d33a1-7788-4444-9999-abcdef012345/cancel/
```

#### پاسخ موفق (HTTP 200 OK):
```json
{
  "message": "درخواست با موفقیت لغو شد."
}
```

#### خطای عدم امکان لغو (HTTP 400 Bad Request):
```json
{
  "error": "لغو فقط زمانی ممکن است که درخواست هنوز در انتظار تایید بالادستی باشد."
}
```

---

### ۳. بررسی بالادستی (`POST /api/employee-requests/{id}/superior-review/`)

بالادستی مشخص‌شده یا ادمین سیستم می‌توانند این اکشن را اجرا کنند.

#### الف) تأیید توسط بالادستی:
```json
POST /api/employee-requests/{id}/superior-review/
Content-Type: application/json

{
  "action": "approve",
  "note": "موافقت شد، وظایف به همکار دیگر محول گردید."
}
```

#### ب) رد توسط بالادستی (نوشتن `note` اجباری است):
```json
POST /api/employee-requests/{id}/superior-review/
Content-Type: application/json

{
  "action": "reject",
  "note": "به دلیل تداخل با شیفت فروشگاه امکان‌پذیر نیست."
}
```

> **توجه:** در صورت تایید بالادستی، چنانچه بالادستی دارای نقش `ADMIN` باشد، مرحله ادمین نادیده گرفته شده و وضعیت مستقیماً به `PENDING_FINANCE` می‌رود. در غیر این صورت، به `PENDING_ADMIN` تغییر خواهد یافت.

---

### ۴. بررسی ادمین (`POST /api/employee-requests/{id}/admin-review/`)

فقط کاربران دارای نقش `ADMIN` یا superuser به این اکشن دسترسی دارند. وضعیت درخواست باید `PENDING_ADMIN` باشد.

#### بدنه درخواست:
```json
POST /api/employee-requests/{id}/admin-review/
Content-Type: application/json

{
  "action": "approve",
  "note": "تایید مدیریت مرکزی"
}
```
*(برای رد، مقدار `"action": "reject"` ارسال و فیلد `note` اجباری است).*

---

### ۵. بررسی مدیر مالی (`POST /api/employee-requests/{id}/finance-review/`)

کاربران دارای نقش `FINANCIAL_MANAGER` یا `ADMIN` به این بخش دسترسی دارند. وضعیت درخواست باید `PENDING_FINANCE` باشد.

#### الف) تایید مساعده و ثبت تاریخ پرداخت:
> **مهم:** برای درخواست‌های نوع مساعده (`ADVANCE`)، فیلد `payment_date` (تاریخ انجام واریز) اجباری است. پس از تایید، وضعیت به `PAID` تغییر می‌کند.

```json
POST /api/employee-requests/{id}/finance-review/
Content-Type: application/json

{
  "action": "approve",
  "payment_date": "2026-11-04",
  "note": "واریز از حساب بانک ملت شعبه مرکزی صورت پذیرفت - کد پیگیری ۸۴۹۲۰۱"
}
```

#### ب) تایید سایر درخواست‌ها (مرخصی، اضافه‌کاری، متفرقه):
> پس از تایید، وضعیت درخواست به `APPROVED` تغییر می‌کند.

```json
POST /api/employee-requests/{id}/finance-review/
Content-Type: application/json

{
  "action": "approve",
  "note": "در سیستم ثبت حضور و غیاب اعمال گردید."
}
```

#### ج) رد درخواست توسط مدیر مالی:
```json
POST /api/employee-requests/{id}/finance-review/
Content-Type: application/json

{
  "action": "reject",
  "note": "سقف بودجه مساعده ماه جاری پر شده است."
}
```

---

### ۶. کارتابل کارمندان و بالادستان (`GET /api/employee-requests/my-inbox/`)

این Endpoint لیست درخواست‌هایی را برمی‌گرداند که کاربر جاری به عنوان **بالادستی** انتخاب شده است.

#### پارامترهای اختیاری Query String:
* `status`: فیلتر وضعیت (مثلاً `PENDING_SUPERIOR` برای مواردی که نیاز به اقدام دارند)
* `request_type`: فیلتر نوع درخواست (`LEAVE`, `ADVANCE`, `OVERTIME`, `MISC`)
* `from_date` و `to_date`: بازه زمانی تاریخ ثبت (فرمت: `YYYY-MM-DD`)
* `search`: جستجو در نام، نام خانوادگی، یا نام کاربری درخواست‌کننده

```http
GET /api/employee-requests/my-inbox/?status=PENDING_SUPERIOR
```

---

### ۷. لیست جامع ادمین و مدیر مالی (`GET /api/employee-requests/admin-list/`)

این Endpoint به مدیران و ادمین‌های سیستم اجازه می‌دهد تمامی درخواست‌ها را به همراه جزئیات کامل و تاریخچه لاگ‌ها مانیتور کنند.

#### پارامترهای اختیاری Query String:
* `status`: فیلتر بر اساس وضعیت
* `request_type`: فیلتر بر اساس نوع درخواست
* `requester_id`: فیلتر بر اساس شناسه کارمند درخواست‌دهنده
* `superior_id`: فیلتر بر اساس شناسه بالادستی
* `from_date` و `to_date`: بازه تاریخ ثبت
* `search`: جستجو در مشخصات فردی کارمند

```http
GET /api/employee-requests/admin-list/?request_type=ADVANCE&status=PAID
```

---

## 📊 ۵. جداول وضعیت‌ها و مراحل (Enums Reference)

### مقادیر وضعیت (`status`):
| مقدار در دیتابیس | عنوان فارسی | توضیحات |
|---|---|---|
| `PENDING_SUPERIOR` | در انتظار تایید بالادستی | وضعیت اولیه پس از ثبت توسط کارمند |
| `REJECTED_BY_SUPERIOR` | رد شده توسط بالادستی | توسط بالادستی رد شده است |
| `PENDING_ADMIN` | در انتظار تایید ادمین | توسط بالادستی تایید شده و منتظر تایید ادمین است |
| `REJECTED_BY_ADMIN` | رد شده توسط ادمین | توسط ادمین رد شده است |
| `PENDING_FINANCE` | در انتظار تایید مدیر مالی | در کارتابل مدیر مالی منتظر بررسی/واریز است |
| `REJECTED_BY_FINANCE` | رد شده توسط مدیر مالی | توسط امور مالی رد شده است |
| `APPROVED` | تایید نهایی | برای مرخصی، اضافه‌کاری و متفرقه |
| `PAID` | پرداخت شده (مساعده) | فقط برای مساعده پس از ثبت پرداخت مالی |
| `CANCELLED` | لغو شده توسط کارمند | لغو شده قبل از بررسی |

### مقادیر مراحل لاگ (`stage` در `EmployeeRequestLog`):
| مقدار مرحله | عنوان فارسی |
|---|---|
| `SUBMIT` | ثبت درخواست |
| `SUPERIOR` | بررسی بالادستی |
| `ADMIN` | بررسی ادمین |
| `FINANCE` | بررسی مدیر مالی |
| `CANCEL` | لغو توسط کارمند |

---

## 🔒 ۶. ماتریس دسترسی و سطوح مجوز (RBAC)

| عملیات | کاربر عادی (کارمند) | بالادستی مشخص‌شده | ادمین (`ADMIN`) | مدیر مالی (`FINANCIAL_MANAGER`) |
|---|:---:|:---:|:---:|:---:|
| **ثبت درخواست** | ✅ | ✅ | ✅ | ✅ |
| **مشاهده درخواست‌های خود** | ✅ | ✅ | ✅ | ✅ |
| **لغو درخواست خود** | ✅ (فقط در انتظار بالادست) | — | — | — |
| **بررسی بالادستی** | ❌ | ✅ | ✅ | ❌ |
| **بررسی ادمین** | ❌ | ❌ | ✅ | ❌ |
| **بررسی و پرداخت مالی** | ❌ | ❌ | ✅ | ✅ |
| **مشاهده `my-inbox`** | ❌ | ✅ | ✅ | ✅ |
| **مشاهده `admin-list`** | ❌ | ❌ | ✅ | ✅ |
| **حذف رکورد** | ❌ | ❌ | ✅ | ❌ |

---

## 🛠️ ۷. نکات فنی و اعتبارسنجی‌ها (Validation Rules)

1. **اعتبارسنجی بالادست:** اگر کاربر بیش از یک بالادست داشته باشد و فیلد `superior_id` را ارسال نکند، خطای `400 Bad Request` با کلید `superior_id` بازگردانده می‌شود. همچنین کاربر نمی‌تواند کسی را انتخاب کند که در لیست بالادستان تعریف‌شده او در مدل `CustomUser.superiors` قرار ندارد.
2. **اعتبارسنجی فیلدهای شرطی نوع:**
   * در صورت انتخاب `LEAVE`، ارسال `leave_mode` الزامی است. برای `DAILY` فیلد `leave_days` (آرایه رشته‌ای تاریخ‌ها) و برای `HOURLY` فیلد `leave_day` الزامی است.
   * در صورت انتخاب `ADVANCE`، فیلد `advance_amount` الزامی و عددی مثبت است.
   * در صورت انتخاب `OVERTIME`، ارسال `overtime_day` و بازه زمانی `overtime_start` و `overtime_end` الزامی است.
   * در صورت انتخاب `MISC`، ارسال `misc_title` الزامی است.
3. **تراکنش‌های اتمیک (`@transaction.atomic`):** تمامی اکشن‌های بررسی، ثبت لاگ و تغییر وضعیت در تراکنش‌های مستقل دیتابیسی اجرا می‌شوند تا در صورت بروز هرگونه خطا داده‌های لاگ و رکورد اصلی دچار ناهمگونی نشوند.
4. **مستندات Swagger / OpenAPI:** کلیه پارامترها و پاسخ‌ها از طریق کتابخانه `drf-spectacular` به شکل استاندارد پیاده‌سازی شده و در صفحه Swagger UI پروژه تحت تگ **«درخواست کارکنان»** در دسترس هستند.
