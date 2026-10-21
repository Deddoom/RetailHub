# 📦 مستندات جامع API — سیستم ثبت خسارت و ضایعات چندمرحله‌ای (Damage Registration)

> **مسیر ریشه API:** `/api/damage-registrations/`  
> **احراز هویت:** `Authorization: Bearer <access_token>` (Stateless Token)

---

## 🌟 ۱. نمای کلی سیستم (Overview)

سیستم ثبت خسارت و اقلام ضایعات در فروشگاه‌ها و شعب، جهت ثبت رسمی کالاها و گیاهان آسیب‌دیده با فرآیند تایید سه‌مرحله‌ای طراحی شده است:

1. **ثبت‌کننده:** فقط سرپرستان شعب (`SUPERVISOR`) یا ادمین کل (`ADMIN`) می‌توانند ضایعات را ثبت نمایند.
2. **انتخاب خودکار سرپرست:** فیلد `supervisor` به صورت پیش‌فرض همان سرپرست ثبت‌کننده در نظر گرفته می‌شود (در صورت ارسال `supervisor_id` در بدنه درخواست نیز اعمال می‌گردد).
3. **مرحله ۱ — تایید انباردار:** رکورد پس از ثبت اولیه در وضعیت `PENDING_WAREHOUSE` قرار می‌گیرد و توسط انباردار (`WAREHOUSE`) یا آمارگیر (`STATISTICIAN`) با ثبت توضیحات اختیاری بررسی و تایید/رد می‌شود.
4. **مرحله ۲ — تایید مدیریت:** پس از تایید انباردار، رکورد در وضعیت `PENDING_MANAGEMENT` قرار می‌گیرد و توسط مدیریت (`ADMIN` یا `EXECUTIVE_MANAGER`) با ثبت توضیحات اختیاری بررسی و تایید/رد می‌شود.
5. **مرحله ۳ — تایید مدیر مالی:** پس از تایید مدیریت، رکورد در وضعیت `PENDING_FINANCIAL` قرار می‌گیرد و توسط مدیر مالی (`FINANCIAL_MANAGER`) با توضیحات اختیاری تایید نهایی (`APPROVED`) یا رد (`REJECTED`) می‌گردد.
6. **دسترسی‌های دیداری:**
   - **مدیر مالی، انباردار، آمارگیر و ادمین:** دسترسی کامل به **تمام ضایعات** ثبت‌شده در سیستم.
   - **سرپرست:** فقط ضایعات ثبت‌شده توسط خودش را مشاهده می‌کند.
7. **امکان لغو توسط سرپرست ثبت‌کننده:** سرپرست ثبت‌کننده تا قبل از بررسی و تایید انباردار (در وضعیت `PENDING_WAREHOUSE`) می‌تواند رکورد خود را لغو کند (`CANCELLED`).
8. **تاریخچه رویدادها (Audit Log):** تمام اقدامات و تاییدها در جدول `DamageRegistrationLog` با ذکر کاربر عامل، مرحله، تاریخ و زمان و توضیحات ثبت می‌شود.

---

## 🔄 ۲. نمودار چرخه حیات (Workflow State Machine)

```
[ثبت ضایعات توسط سرپرست یا ادمین]
              │
              ▼
  [در انتظار تایید انباردار (PENDING_WAREHOUSE)]
      ├── [لغو توسط سرپرست (CANCELLED)] (فقط قبل از بررسی انباردار)
      ├── [رد توسط انباردار (REJECTED)]
      └── [تایید توسط انباردار یا آمارگیر]
              │
              ▼
  [در انتظار تایید مدیریت (PENDING_MANAGEMENT)]
      ├── [رد توسط مدیریت (REJECTED)]
      └── [تایید توسط مدیریت (توضیحات اختیاری)]
              │
              ▼
  [در انتظار تایید مدیر مالی (PENDING_FINANCIAL)]
      ├── [رد توسط مدیر مالی (REJECTED)]
      └── [تایید نهایی توسط مدیر مالی (APPROVED)]
```

---

## 📑 ۳. جدول خلاصه Endpointها

| متد | آدرس Endpoint | شرح عملکرد | دسترسی و نقش‌های مجاز |
|---|---|---|---|
| `GET` | `/api/damage-registrations/` | لیست ثبت‌های ضایعات (خلاصه) | 🔐 سرپرستان (فقط مال خود)، انبارداران، مدیر مالی و ادمین (همه) |
| `POST` | `/api/damage-registrations/` | ثبت ضایعات و اقلام جدید | 🔐 سرپرست شعبه یا ادمین سیستم |
| `GET` | `/api/damage-registrations/{id}/` | مشاهده جزئیات کامل رکورد + اقلام + لاگ‌ها | 🔐 سرپرست مربوطه، انباردار، مدیر مالی، ادمین |
| `PUT/PATCH`| `/api/damage-registrations/{id}/` | ویرایش رکورد (فقط قبل از بررسی انباردار) | 🔐 سرپرست ثبت‌کننده یا ادمین |
| `POST` | `/api/damage-registrations/{id}/warehouse-review/` | مرحله ۱: تایید یا رد ضایعات توسط انباردار | 👑 انباردار، آمارگیر یا ادمین |
| `POST` | `/api/damage-registrations/{id}/management-review/` | مرحله ۲: تایید یا رد ضایعات توسط مدیریت | 👑 مدیریت سیستم (ادمین یا مدیر اجرایی) |
| `POST` | `/api/damage-registrations/{id}/financial-review/` | مرحله ۳: تایید نهایی یا رد توسط مدیر مالی | 👑 مدیر مالی یا ادمین سیستم |
| `POST` | `/api/damage-registrations/{id}/cancel/` | لغو ثبت ضایعات توسط سرپرست ثبت‌کننده | 🔐 فقط سرپرست ثبت‌کننده (در وضعیت انتظار انباردار) |
| `GET` | `/api/damage-registrations/my-inbox/` | کارتابل ضایعات (موارد منتظر اقدام کاربر فعال) | 👑 متناسب با نقش کاربر فعال |
| `DELETE` | `/api/damage-registrations/{id}/` | حذف گزارش ضایعات | 👑 ادمین |

---

## 🔍 ۴. شرح دقیق Endpointها و نمونه Payloadها

### ۱. ثبت ضایعات جدید (`POST /api/damage-registrations/`)

**دسترسی:** فقط کاربران دارای نقش `SUPERVISOR` (سرپرست شعبه) یا `ADMIN` (مدیریت).

#### بدنه درخواست (Request Body):
```json
POST /api/damage-registrations/
Content-Type: application/json

{
  "date": "2026-10-22",
  "branch": "شعبه بهشتی",
  "reason": "BREAKAGE",
  "culprit": "واحد حمل بار",
  "description": "شکستگی در هنگام تخلیه بار در انبار شعبه بهشتی",
  "items": [
    {
      "item_name": "گلدان سرامیکی طرح کلاسیک",
      "quantity": 4,
      "unit_price": "180000.00"
    },
    {
      "item_name": "پایه چوبی گلدان",
      "quantity": 2,
      "unit_price": "250000.00"
    }
  ]
}
```

> **نکته:** فیلد `supervisor_id` اختیاری است. اگر ارسال نشود، به صورت خودکار کاربر لاگین‌شده سرپرست به عنوان سرپرست رکورد ثبت می‌گردد.

#### پاسخ موفق (HTTP 201 Created):
```json
{
  "id": "a95b3d68-d01f-4952-b13c-abcdef123456",
  "date": "2026-10-22",
  "branch": "شعبه بهشتی",
  "reason": "BREAKAGE",
  "reason_display": "شکستگی",
  "culprit": "واحد حمل بار",
  "description": "شکستگی در هنگام تخلیه بار در انبار شعبه بهشتی",
  "status": "PENDING_WAREHOUSE",
  "status_display": "در انتظار تایید انباردار",
  "created_by": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "created_by_name": "رضا صادقی (سرپرست)",
  "created_by_username": "reza_sup",
  "supervisor": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "supervisor_name": "رضا صادقی (سرپرست)",
  "supervisor_username": "reza_sup",
  "warehouse_reviewer": null,
  "warehouse_reviewer_name": null,
  "warehouse_note": null,
  "warehouse_reviewed_at": null,
  "management_reviewer": null,
  "management_reviewer_name": null,
  "management_note": null,
  "management_reviewed_at": null,
  "financial_reviewer": null,
  "financial_reviewer_name": null,
  "financial_note": null,
  "financial_reviewed_at": null,
  "items": [
    {
      "id": "84d5f0b1-...",
      "item_name": "گلدان سرامیکی طرح کلاسیک",
      "quantity": 4,
      "unit_price": "180000.00",
      "total_price": "720000.00"
    }
  ],
  "logs": [
    {
      "stage": "SUBMIT",
      "stage_display": "ثبت اولیه توسط سرپرست",
      "actor_name": "رضا صادقی",
      "action": "ثبت اولیه ضایعات شعبه بهشتی توسط سرپرست (رضا صادقی) و ارجاع به انباردار جهت بررسی",
      "created_at": "2026-10-22T08:30:00Z"
    }
  ],
  "created_at": "2026-10-22T08:30:00Z",
  "updated_at": "2026-10-22T08:30:00Z"
}
```

---

### ۲. مرحله ۱: تایید یا رد توسط انباردار (`POST /api/damage-registrations/{id}/warehouse-review/`)

**دسترسی:** کاربران دارای نقش `WAREHOUSE` (انباردار)، `STATISTICIAN` (آمارگیر) یا `ADMIN`.

#### بدنه درخواست:
```json
POST /api/damage-registrations/{id}/warehouse-review/
Content-Type: application/json

{
  "action": "approve",
  "note": "اقلام از نزدیک مشاهده و تایید گردید."
}
```
* `action`: مقدار `approve` (تایید و ارجاع به مدیریت) یا `reject` (رد گزارش ضایعات).
* `note`: اختیاری.

#### پاسخ موفق:
```json
{
  "message": "گزارش ضایعات با موفقیت تایید و به مدیریت ارجاع شد."
}
```

---

### ۳. مرحله ۲: تایید یا رد توسط مدیریت (`POST /api/damage-registrations/{id}/management-review/`)

**دسترسی:** کاربران دارای نقش `ADMIN` یا `EXECUTIVE_MANAGER`.

#### بدنه درخواست:
```json
POST /api/damage-registrations/{id}/management-review/
Content-Type: application/json

{
  "action": "approve",
  "note": "مورد تایید مدیریت است."
}
```
* فیلد `note` در این مرحله **کاملاً اختیاری** است (می‌توان ارسال نکرد یا خالی گذاشت).

#### پاسخ موفق:
```json
{
  "message": "گزارش ضایعات با موفقیت تایید و به مدیر مالی ارجاع شد."
}
```

---

### ۴. مرحله ۳: تایید نهایی یا رد توسط مدیر مالی (`POST /api/damage-registrations/{id}/financial-review/`)

**دسترسی:** کاربران دارای نقش `FINANCIAL_MANAGER` (مدیر مالی) یا `ADMIN`.

#### بدنه درخواست:
```json
POST /api/damage-registrations/{id}/financial-review/
Content-Type: application/json

{
  "action": "approve",
  "note": "تایید نهایی و اعمال در تراز مالیات و ضایعات دوره"
}
```

#### پاسخ موفق:
```json
{
  "message": "گزارش ضایعات با موفقیت تایید نهایی شد."
}
```

---

### ۵. لغو توسط سرپرست ثبت‌کننده (`POST /api/damage-registrations/{id}/cancel/`)

**دسترسی:** فقط کاربر ثبت‌کننده سرپرست (یا ادمین) تا قبل از بررسی و تایید انباردار (`PENDING_WAREHOUSE`).

```json
POST /api/damage-registrations/{id}/cancel/
```

#### پاسخ موفق:
```json
{
  "message": "گزارش ضایعات با موفقیت لغو شد."
}
```

---

### ۶. کارتابل هوشمند کاربر (`GET /api/damage-registrations/my-inbox/`)

این Endpoint به طور هوشمند بر اساس نقش کاربر درخواست‌دهنده، موارد نیازمند اقدام را برمی‌گرداند:
* برای **انباردار و آمارگیر:** موارد در انتظار تایید انباردار (`PENDING_WAREHOUSE`).
* برای **مدیریت:** موارد در انتظار تایید مدیریت (`PENDING_MANAGEMENT`).
* برای **مدیر مالی:** موارد در انتظار تایید مدیر مالی (`PENDING_FINANCIAL`).
* برای **سرپرست:** کلیه ضایعات ثبت‌شده توسط او جهت پیگیری وضعیت گردش کار.

---

## 🔒 ۵. ماتریس وضعیت‌ها و دسترسی‌ها

| کد وضعیت | عنوان فارسی | اقدام بعدی | بررسی‌کننده مجاز |
|---|---|---|---|
| `PENDING_WAREHOUSE` | در انتظار تایید انباردار | بررسی میدانی اقلام | انباردار / آمارگیر |
| `PENDING_MANAGEMENT` | در انتظار تایید مدیریت | بررسی سیستمی و تایید اولیه | مدیریت (Admin / مدیر اجرایی) |
| `PENDING_FINANCIAL` | در انتظار تایید مدیر مالی | بررسی و تایید نهایی مالی | مدیر مالی |
| `APPROVED` | تایید نهایی شده | پرونده بسته و تایید شد | — |
| `REJECTED` | رد شده | گزارش رد شد | — |
| `CANCELLED` | لغو شده | لغو توسط ثبت‌کننده | — |
