# 📖 مستندات کامل API — RetailHub
> ویژه برنامه‌نویسان فرانت‌اند (React / Vue / Flutter / iOS / Android)
> مجموع Endpointها: **56 endpoint**

---

## 🌐 Base URL

```
http://185.213.164.106/api/
```

---

## 🔑 احراز هویت

### مکانیزم کلی

سیستم از **Stateless Token** مبتنی بر امضای دیجیتال استفاده می‌کند (نه JWT استاندارد):

| توکن | مدت اعتبار | محل ذخیره |
|---|---|---|
| Access Token | ۱۵ دقیقه | حافظه جاوااسکریپت (نه localStorage) |
| Refresh Token | ۷ روز | کوکی HttpOnly (خودکار توسط مرورگر مدیریت می‌شود) |

### هدر الزامی برای تمام درخواست‌ها (به جز Login و Refresh)

```
Authorization: Bearer <access_token>
```

### نقش‌های کاربری

| نقش | توضیح | دسترسی |
|---|---|---|
| `ADMIN` | مدیر سیستم | دسترسی کامل به همه چیز |
| `CASHIER` | صندوق‌دار | خواندن همه + ویرایش فقط رکوردهای خودش |
| `USER` | کارمند عادی | خواندن + تغییر وضعیت تسک‌ها |

---

## 📌 نمادهای این سند

| نماد | معنی |
|---|---|
| 🔓 | نیاز به احراز هویت ندارد |
| 🔐 | نیاز به احراز هویت دارد |
| 👑 | فقط ADMIN |
| 🏪 | ADMIN + CASHIER (خواندن) |
| 📝 | فقط رکوردهای خودت (CASHIER) یا همه (ADMIN) |
| ⚙️ | فیلد خودکار — نباید ارسال شود |
| ✴️ | فیلد اجباری |

---

---

# ۱. احراز هویت (Auth)

---

## 1.1 ورود به سیستم — Login

```
POST /api/auth/token/
```

**دسترسی:** 🔓 عمومی

### Request Body

```json
{
  "username": "admin",
  "password": "admin1234"
}
```

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `username` | string | ✴️ | نام کاربری |
| `password` | string | ✴️ | رمز عبور |

### Response — 200 OK

```json
{
  "access_token": "eyJ...[Base64_Encoded_Signed_Token]",
  "role": "ADMIN",
  "branch": "دفتر مرکزی"
}
```

| فیلد | توضیح |
|---|---|
| `access_token` | توکن دسترسی — در هدر Authorization استفاده کنید |
| `role` | نقش کاربر: `ADMIN` / `CASHIER` / `USER` |
| `branch` | شعبه کاربر — برای نمایش در UI |

> یک کوکی **HttpOnly** با نام `refresh_token` نیز خودکار روی مرورگر ست می‌شود.

### Response — خطاها

```json
// 400 — فیلد خالی
{ "error": "نام کاربری و رمز عبور الزامی است." }

// 401 — مشخصات اشتباه
{ "error": "مشخصات نامعتبر است." }

// 403 — حساب غیرفعال
{ "error": "حساب کاربری غیرفعال است." }
```

### نمونه کد (JavaScript)

```javascript
const login = async (username, password) => {
  const res = await fetch('http://185.213.164.106/api/auth/token/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include', // الزامی برای دریافت کوکی refresh_token
    body: JSON.stringify({ username, password })
  });
  const data = await res.json();
  // access_token را در حافظه نگه دارید (نه localStorage)
  // refresh_token به صورت خودکار در کوکی ذخیره می‌شود
  return data; // { access_token, role, branch }
};
```

---

## 1.2 تمدید توکن — Refresh Token

```
POST /api/auth/token/refresh/
```

**دسترسی:** 🔓 عمومی

### روش اول — از کوکی (پیشنهادی)

وقتی `credentials: 'include'` باشد، مرورگر کوکی `refresh_token` را خودکار ارسال می‌کند.

```json
{}
```

### روش دوم — از Body

```json
{
  "refresh_token": "eyJ...[Base64_Encoded_Signed_Token]"
}
```

### Response — 200 OK

```json
{
  "access_token": "eyJ...[New_Access_Token]"
}
```

> کوکی refresh_token نیز با مقدار جدید به‌روز می‌شود.

### Response — خطاها

```json
// 400 — توکن ارسال نشده
{ "error": "توکن یافت نشد." }

// 401 — توکن نامعتبر یا منقضی
{ "error": "توکن نامعتبر است." }
```

### نمونه کد — مدیریت خودکار تمدید توکن

```javascript
let accessToken = null;

const apiCall = async (url, options = {}) => {
  const res = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`,
      ...options.headers
    }
  });

  if (res.status === 401) {
    // توکن منقضی شده — تمدید کن
    const refreshRes = await fetch('http://185.213.164.106/api/auth/token/refresh/', {
      method: 'POST',
      credentials: 'include'
    });
    if (!refreshRes.ok) {
      // Refresh token هم منقضی شده — باید دوباره لاگین کند
      window.location.href = '/login';
      return;
    }
    const { access_token } = await refreshRes.json();
    accessToken = access_token;
    // درخواست اصلی را تکرار کن
    return apiCall(url, options);
  }
  return res.json();
};
```

---

---

# ۲. کاربران — Users

> 👑 تمام عملیات فقط ADMIN

---

## 2.1 لیست کاربران

```
GET /api/users/
```

### Response — 200 OK

```json
[
  {
    "id": "uuid",
    "username": "admin",
    "role": "ADMIN",
    "branch": "دفتر مرکزی",
    "is_active": true
  }
]
```

---

## 2.2 ثبت کاربر جدید

```
POST /api/users/
```

### Request Body

```json
{
  "username": "cashier2",
  "password": "StrongPass1234",
  "role": "CASHIER",
  "branch": "شعبه ولیعصر",
  "is_active": true
}
```

| فیلد | نوع | اجباری | مقادیر مجاز |
|---|---|---|---|
| `username` | string | ✴️ | — |
| `password` | string | ✴️ | — (write-only) |
| `role` | string | ✴️ | `ADMIN` / `CASHIER` / `USER` |
| `branch` | string | — | نام شعبه |
| `is_active` | boolean | — | پیش‌فرض: `true` |

### Response — 201 Created

```json
{
  "id": "3f2a1b...",
  "username": "cashier2",
  "role": "CASHIER",
  "branch": "شعبه ولیعصر",
  "is_active": true
}
```

> `password` در response نمایش داده نمی‌شود.

---

## 2.3 مشاهده کاربر خاص

```
GET /api/users/{user_uuid}/
```

---

## 2.4 ویرایش کامل کاربر

```
PUT /api/users/{user_uuid}/
```

همه فیلدهای 2.2 لازم است.

---

## 2.5 ویرایش جزئی کاربر

```
PATCH /api/users/{user_uuid}/
```

مثال — غیرفعال کردن کاربر:

```json
{
  "is_active": false
}
```

---

## 2.6 حذف کاربر

```
DELETE /api/users/{user_uuid}/
```

### Response — 204 No Content

---

---

# ۳. فروشندگان — Sellers

---

## 3.1 لیست فروشندگان

```
GET /api/sellers/
```

**دسترسی:** 🔐 همه کاربران احراز هویت‌شده

### Response — 200 OK

```json
[
  {
    "id": "uuid",
    "name": "امیر قاسمی",
    "phone": "09120001122",
    "branch": "شعبه پاسداران"
  }
]
```

---

## 3.2 ثبت فروشنده جدید

```
POST /api/sellers/
```

**دسترسی:** 👑 فقط ADMIN

### Request Body

```json
{
  "name": "سارا احمدی",
  "phone": "09131112233",
  "branch": "شعبه ولیعصر"
}
```

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `name` | string | ✴️ | نام کامل فروشنده |
| `phone` | string | — | شماره موبایل (یکتا) |
| `branch` | string | ✴️ | نام شعبه |

---

## 3.3 مشاهده فروشنده خاص

```
GET /api/sellers/{seller_uuid}/
```

**دسترسی:** 🔐 همه

---

## 3.4 ویرایش فروشنده

```
PUT  /api/sellers/{seller_uuid}/
PATCH /api/sellers/{seller_uuid}/
```

**دسترسی:** 👑 فقط ADMIN

---

## 3.5 حذف فروشنده

```
DELETE /api/sellers/{seller_uuid}/
```

**دسترسی:** 👑 فقط ADMIN

> ⚠️ اگر فروشنده فاکتور داشته باشد، حذف با خطای `PROTECT` مسدود می‌شود.

---

---

# ۴. مشتریان — Customers

**دسترسی:** 🔐 همه کاربران احراز هویت‌شده (همه عملیات)

---

## 4.1 لیست مشتریان

```
GET /api/customers/
```

### Response — 200 OK

```json
[
  {
    "id": "uuid",
    "name": "علیرضا فتاحی",
    "phone": "09154445566",
    "address": "تهران، خیابان آزادی",
    "primary_goods": "NEHAL",
    "buying_for": "GARDEN",
    "last_purchase_date": "2026-06-01",
    "total_purchase_amount": "12500000.00",
    "last_purchase_type": "CHEQUE",
    "description": "مشتری VIP"
  }
]
```

---

## 4.2 ثبت مشتری جدید

```
POST /api/customers/
```

### Request Body

```json
{
  "name": "رضا محمدی",
  "phone": "09361234567",
  "address": "اصفهان، خیابان چهارباغ",
  "primary_goods": "POT",
  "buying_for": "HOUSE",
  "description": "مشتری عمده‌فروش"
}
```

| فیلد | نوع | اجباری | مقادیر مجاز |
|---|---|---|---|
| `name` | string | ✴️ | — |
| `phone` | string | ✴️ | یکتا در کل سیستم |
| `address` | string | — | — |
| `primary_goods` | string | — | `APARTMENT` / `OUTDOOR` / `FERTILIZER` / `NEHAL` / `POT` / `OTHER` |
| `buying_for` | string | — | `GARDEN` / `HOUSE` / `SHOP` / `OTHER` |
| `description` | string | — | — |

> فیلدهای `last_purchase_date`، `total_purchase_amount`، `last_purchase_type` **خودکار** هنگام ثبت فاکتور فروش به‌روز می‌شوند و نباید ارسال شوند.

---

## 4.3 مشاهده مشتری خاص

```
GET /api/customers/{customer_uuid}/
```

---

## 4.4 ویرایش مشتری

```
PUT   /api/customers/{customer_uuid}/
PATCH /api/customers/{customer_uuid}/
```

مثال — ویرایش آدرس:

```json
{
  "address": "تهران، ولنجک"
}
```

---

## 4.5 حذف مشتری

```
DELETE /api/customers/{customer_uuid}/
```

> ⚠️ اگر مشتری فاکتور داشته باشد، حذف با خطای `PROTECT` مسدود می‌شود.

---

---

# ۵. فاکتورهای فروش — Sales

**دسترسی:** 📝 ADMIN همه فاکتورها را می‌بیند — CASHIER/USER فقط فاکتورهای خودشان را

---

## 5.1 لیست فاکتورها

```
GET /api/sales/
```

### Response — 200 OK

```json
[
  {
    "id": "uuid",
    "total_amount": "5500000.00",
    "remaining_balance": "0.00",
    "date_time": "2026-06-07T10:30:00+03:30",
    "branch": "شعبه پاسداران",
    "seller": { "id": "uuid", "name": "امیر قاسمی", "phone": "...", "branch": "..." },
    "customer": { "id": "uuid", "name": "علیرضا فتاحی", ... },
    "created_by": "admin (مدیر سیستم)",
    "description": "فروش نهال",
    "payments": [ ... ],
    "deposit_items": [ ... ]
  }
]
```

---

## 5.2 ثبت فاکتور فروش جدید

```
POST /api/sales/
```

**مهم:** قبل از ثبت فاکتور باید UUID مشتری و فروشنده را از APIهای مربوطه دریافت کنید.

### Request Body — ساده‌ترین حالت (پرداخت نقدی)

```json
{
  "total_amount": "2000000.00",
  "branch": "شعبه پاسداران",
  "seller": "uuid-فروشنده",
  "customer": "uuid-مشتری",
  "description": "فروش گلدان",
  "payments": [
    {
      "payment_method": "CASH",
      "amount": "2000000.00",
      "description": "پرداخت نقدی کامل"
    }
  ]
}
```

### Request Body — پرداخت ترکیبی با چک و بیعانه

```json
{
  "total_amount": "5500000.00",
  "branch": "شعبه پاسداران",
  "seller": "uuid-فروشنده",
  "customer": "uuid-مشتری",
  "description": "فروش نهال به همراه بیعانه گلدان سفالی",
  "payments": [
    {
      "payment_method": "CHEQUE",
      "amount": "3000000.00",
      "description": "چک صیادی بانک ملی",
      "cheques": [
        {
          "due_date": "2026-08-20",
          "cheque_number": "1234/5678-Melli",
          "amount": "3000000.00",
          "customer_phone": "09154445566",
          "customer_name": "علیرضا فتاحی",
          "description": "چک ثبت شده در سامانه صیاد"
        }
      ]
    },
    {
      "payment_method": "DEPOSIT",
      "amount": "2500000.00",
      "description": "بیعانه بابت گلدان‌ها"
    }
  ],
  "deposit_items": [
    {
      "item_name": "گلدان سفالی بزرگ درجه ۱",
      "quantity": 10,
      "unit_price": "250000.00"
    }
  ]
}
```

### فیلدهای Sale

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `total_amount` | decimal | ✴️ | مبلغ کل فاکتور |
| `branch` | string | ✴️ | نام شعبه |
| `seller` | uuid | ✴️ | شناسه فروشنده |
| `customer` | uuid | ✴️ | شناسه مشتری |
| `description` | string | — | توضیح فاکتور |
| `payments` | array | — | لیست پرداخت‌ها |
| `deposit_items` | array | — | اقلام بیعانه (اجباری اگر payment_method=DEPOSIT) |
| `remaining_balance` | decimal | ⚙️ | خودکار = total_amount - sum(payments) |
| `date_time` | datetime | ⚙️ | خودکار |
| `created_by` | string | ⚙️ | خودکار از توکن |

### فیلدهای Payment (داخل payments[])

| فیلد | نوع | اجباری | مقادیر مجاز |
|---|---|---|---|
| `payment_method` | string | ✴️ | `CASH` / `CARD_TO_CARD` / `SHEBA` / `POS` / `COMBINED` / `REMAINING` / `DEPOSIT` / `CHEQUE` |
| `amount` | decimal | ✴️ | مبلغ این پرداخت |
| `description` | string | — | توضیح |
| `cheques` | array | — | فقط برای `CHEQUE` و `COMBINED` |

### فیلدهای Cheque (داخل payments[].cheques[])

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `cheque_number` | string | ✴️ | شماره چک (یکتا در کل سیستم) |
| `due_date` | date | ✴️ | تاریخ سررسید (YYYY-MM-DD) |
| `amount` | decimal | ✴️ | مبلغ چک |
| `customer_phone` | string | — | پیش‌فرض: شماره مشتری فاکتور |
| `customer_name` | string | — | پیش‌فرض: نام مشتری فاکتور |
| `description` | string | — | — |

### فیلدهای DepositItem (داخل deposit_items[])

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `item_name` | string | ✴️ | نام کالا |
| `quantity` | integer | ✴️ | تعداد |
| `unit_price` | decimal | ✴️ | قیمت واحد |
| `total_price` | decimal | ⚙️ | خودکار = quantity × unit_price |

### قوانین اعتبارسنجی فاکتور

- مجموع `amount` در payments نمی‌تواند از `total_amount` بیشتر باشد
- اگر `payment_method == DEPOSIT` باشد، حتماً باید `deposit_items` هم ارسال شود
- `cheque_number` باید در کل سیستم یکتا باشد

### Response — 201 Created

فاکتور کامل با تمام nested objectها برگردانده می‌شود.

---

## 5.3 مشاهده فاکتور خاص

```
GET /api/sales/{sale_uuid}/
```

---

## 5.4 ویرایش فاکتور

```
PUT   /api/sales/{sale_uuid}/
PATCH /api/sales/{sale_uuid}/
```

**دسترسی:** ADMIN همه — CASHIER فقط فاکتور خودش

---

## 5.5 حذف فاکتور

```
DELETE /api/sales/{sale_uuid}/
```

**دسترسی:** ADMIN همه — CASHIER فقط فاکتور خودش

---

---

# ۶. هزینه‌ها — Expenses

**دسترسی:** 📝 ADMIN همه هزینه‌ها — CASHIER/USER فقط هزینه‌های خودشان

---

## 6.1 لیست هزینه‌ها

```
GET /api/expenses/
```

### Response — 200 OK

```json
[
  {
    "id": "uuid",
    "amount": "1500000.00",
    "payment_method": "CHEQUE",
    "date": "2026-06-05",
    "category": "خرید سموم کشاورزی",
    "branch": "شعبه پاسداران",
    "invoice_image_url": "https://storage.example.com/inv.png",
    "created_by": "cashier (صندوق‌دار)",
    "description": "خرید کود مایع",
    "cheques": [ ... ]
  }
]
```

---

## 6.2 ثبت هزینه جدید

```
POST /api/expenses/
```

### Request Body — هزینه نقدی ساده

```json
{
  "amount": "500000.00",
  "payment_method": "CASH",
  "date": "2026-06-07",
  "category": "هزینه حمل‌ونقل",
  "branch": "شعبه پاسداران",
  "description": "کرایه باربری"
}
```

### Request Body — هزینه با چک جدید

```json
{
  "amount": "3000000.00",
  "payment_method": "CHEQUE",
  "date": "2026-06-07",
  "category": "خرید کود و سم",
  "branch": "شعبه پاسداران",
  "invoice_image_url": "https://storage.example.com/invoices/inv-908.png",
  "description": "خرید کود مایع و سم قارچ‌کش",
  "cheques": [
    {
      "cheque_number": "9999/1111-Saderat",
      "is_endorsed": false,
      "due_date": "2026-09-01",
      "amount": "3000000.00",
      "description": "چک جدید بابت خرید"
    }
  ]
}
```

### Request Body — خرج کردن چک دریافتی از مشتری (ظهرنویسی)

```json
{
  "amount": "3000000.00",
  "payment_method": "CHEQUE",
  "date": "2026-06-07",
  "category": "پرداخت به تامین‌کننده",
  "branch": "شعبه پاسداران",
  "cheques": [
    {
      "cheque_number": "1234/5678-Melli",
      "is_endorsed": true,
      "due_date": "2026-08-20",
      "amount": "3000000.00",
      "description": "چک دریافتی از فتاحی — ظهرنویسی شده"
    }
  ]
}
```

> وقتی `is_endorsed: true` باشد، سیستم چک را در بانک اطلاعاتی پیدا کرده و وضعیتش را به "خرج‌شده" تغییر می‌دهد. اگر چک وجود نداشت، رکورد جدید می‌سازد.

### فیلدهای Expense

| فیلد | نوع | اجباری | مقادیر مجاز |
|---|---|---|---|
| `amount` | decimal | ✴️ | مبلغ هزینه |
| `payment_method` | string | ✴️ | `CASH` / `CARD` / `ACCOUNT_TO_ACCOUNT` / `COMBINED` / `CHEQUE` |
| `date` | date | ✴️ | YYYY-MM-DD |
| `category` | string | ✴️ | دسته‌بندی هزینه |
| `branch` | string | ✴️ | نام شعبه |
| `invoice_image_url` | string | — | لینک عکس فاکتور |
| `description` | string | — | توضیح |
| `cheques` | array | — | فقط برای `CHEQUE` و `COMBINED` |
| `created_by` | string | ⚙️ | خودکار از توکن |

---

## 6.3 مشاهده هزینه خاص

```
GET /api/expenses/{expense_uuid}/
```

---

## 6.4 ویرایش هزینه

```
PUT   /api/expenses/{expense_uuid}/
PATCH /api/expenses/{expense_uuid}/
```

---

## 6.5 حذف هزینه

```
DELETE /api/expenses/{expense_uuid}/
```

---

---

# ۷. گزارش خرابی — Damage Reports

**دسترسی:** 📝 ADMIN همه — CASHIER فقط گزارش‌های خودش — USER فقط خواندن

---

## 7.1 لیست گزارش‌های خرابی

```
GET /api/damage-reports/
```

### Response — 200 OK

```json
[
  {
    "id": "uuid",
    "item_name": "نهال بید مجنون",
    "quantity": 5,
    "estimated_loss": "750000.00",
    "date": "2026-06-07",
    "branch": "شعبه پاسداران",
    "description": "آفت‌زدگی در گلخانه شماره ۲",
    "created_by": "cashier (صندوق‌دار)"
  }
]
```

---

## 7.2 ثبت گزارش خرابی جدید

```
POST /api/damage-reports/
```

### Request Body

```json
{
  "item_name": "نهال بید مجنون",
  "quantity": 5,
  "estimated_loss": "750000.00",
  "date": "2026-06-07",
  "branch": "شعبه پاسداران",
  "description": "آفت‌زدگی در گلخانه شماره ۲"
}
```

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `item_name` | string | ✴️ | نام کالای خراب‌شده |
| `quantity` | integer | ✴️ | تعداد |
| `estimated_loss` | decimal | ✴️ | تخمین خسارت (ریال) |
| `date` | date | ✴️ | YYYY-MM-DD |
| `branch` | string | ✴️ | نام شعبه |
| `description` | string | — | توضیح |
| `created_by` | — | ⚙️ | خودکار از توکن |

---

## 7.3 مشاهده گزارش خاص

```
GET /api/damage-reports/{report_uuid}/
```

---

## 7.4 ویرایش گزارش

```
PUT   /api/damage-reports/{report_uuid}/
PATCH /api/damage-reports/{report_uuid}/
```

---

## 7.5 حذف گزارش

```
DELETE /api/damage-reports/{report_uuid}/
```

---

---

# ۸. خروج کالا — Item Exits

**دسترسی:** 📝 مانند Damage Reports

---

## 8.1 لیست خروج کالا

```
GET /api/item-exits/
```

### Response — 200 OK

```json
[
  {
    "id": "uuid",
    "item_name": "کود NPK 20 کیلویی",
    "quantity": 3,
    "reason": "INTERNAL",
    "date": "2026-06-07",
    "branch": "شعبه پاسداران",
    "created_by": "cashier (صندوق‌دار)"
  }
]
```

---

## 8.2 ثبت خروج کالا

```
POST /api/item-exits/
```

### Request Body

```json
{
  "item_name": "کود NPK 20 کیلویی",
  "quantity": 3,
  "reason": "INTERNAL",
  "date": "2026-06-07",
  "branch": "شعبه پاسداران"
}
```

| فیلد | نوع | اجباری | مقادیر مجاز |
|---|---|---|---|
| `item_name` | string | ✴️ | نام کالا |
| `quantity` | integer | ✴️ | تعداد |
| `reason` | string | ✴️ | `RETURN` (مرجوعی) / `DAMAGE` (خرابی) / `INTERNAL` (مصرف داخلی) |
| `date` | date | ✴️ | YYYY-MM-DD |
| `branch` | string | ✴️ | نام شعبه |
| `created_by` | — | ⚙️ | خودکار از توکن |

---

## 8.3 مشاهده خروج کالا خاص

```
GET /api/item-exits/{exit_uuid}/
```

---

## 8.4 ویرایش

```
PUT   /api/item-exits/{exit_uuid}/
PATCH /api/item-exits/{exit_uuid}/
```

---

## 8.5 حذف

```
DELETE /api/item-exits/{exit_uuid}/
```

---

---

# ۹. چک‌لیست‌ها — Checklists

---

## 9.1 لیست چک‌لیست‌ها

```
GET /api/checklists/
```

**دسترسی:** 🔐 همه کاربران احراز هویت‌شده

### Response — 200 OK

```json
[
  {
    "id": "uuid",
    "title": "وظایف روزانه گلخانه — ۱۴۰۵/۳/۱۷",
    "created_at": "2026-06-07T08:00:00+03:30",
    "created_by": "admin (مدیر سیستم)",
    "tasks": [
      {
        "id": "uuid",
        "title": "آبیاری نهال‌های گلخانه شماره ۲",
        "is_completed": true,
        "completed_by": "uuid-کاربر",
        "completed_at": "2026-06-07T09:30:00+03:30",
        "description": "آبیاری کامل انجام شد"
      }
    ]
  }
]
```

---

## 9.2 ثبت چک‌لیست جدید

```
POST /api/checklists/
```

**دسترسی:** 👑 فقط ADMIN

### Request Body

```json
{
  "title": "وظایف روزانه گلخانه — ۱۴۰۵/۳/۱۸"
}
```

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `title` | string | ✴️ | عنوان چک‌لیست |
| `created_by` | — | ⚙️ | خودکار از توکن |
| `created_at` | — | ⚙️ | خودکار |

> تسک‌ها به صورت جداگانه از طریق API Tasks اضافه می‌شوند.

---

## 9.3 مشاهده چک‌لیست خاص

```
GET /api/checklists/{checklist_uuid}/
```

**دسترسی:** 🔐 همه — شامل تمام تسک‌های nested

---

## 9.4 ویرایش چک‌لیست

```
PUT   /api/checklists/{checklist_uuid}/
PATCH /api/checklists/{checklist_uuid}/
```

**دسترسی:** 👑 فقط ADMIN

---

## 9.5 حذف چک‌لیست

```
DELETE /api/checklists/{checklist_uuid}/
```

**دسترسی:** 👑 فقط ADMIN — همه تسک‌های داخل نیز حذف می‌شوند (CASCADE)

---

---

# ۱۰. تسک‌ها — Tasks

---

## 10.1 لیست تسک‌ها

```
GET /api/tasks/
```

**دسترسی:** 🔐 همه

---

## 10.2 ثبت تسک جدید

```
POST /api/tasks/
```

**دسترسی:** 👑 فقط ADMIN

### Request Body

```json
{
  "checklist": "uuid-چک‌لیست",
  "title": "آبیاری نهال‌های گلخانه شماره ۲"
}
```

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `checklist` | uuid | ✴️ | شناسه چک‌لیست مربوطه |
| `title` | string | ✴️ | عنوان تسک |

---

## 10.3 مشاهده تسک خاص

```
GET /api/tasks/{task_uuid}/
```

---

## 10.4 به‌روزرسانی وضعیت تسک — ✅ مهم‌ترین endpoint برای کاربر عادی

```
PUT   /api/tasks/{task_uuid}/
PATCH /api/tasks/{task_uuid}/
```

**دسترسی:** 🔐 همه — اما محدودیت نقش دارد

### رفتار بر اساس نقش

| نقش | می‌تواند تغییر دهد |
|---|---|
| `ADMIN` | همه فیلدها |
| `CASHIER` | همه فیلدها |
| `USER` | فقط `is_completed` و `description` |

### Request Body — برای USER (کارمند عادی)

```json
{
  "is_completed": true,
  "description": "آبیاری نهال‌های گلخانه شماره ۲ به طور کامل انجام شد."
}
```

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `is_completed` | boolean | — | `true` = انجام شد / `false` = برگشت به ناتمام |
| `description` | string | — | گزارش انجام کار |
| `completed_by` | — | ⚙️ | خودکار — کاربری که `is_completed=true` زده |
| `completed_at` | — | ⚙️ | خودکار — زمان تکمیل |

> اگر `is_completed: false` ارسال شود، مقادیر `completed_by` و `completed_at` به `null` ریست می‌شوند.

### Response — 200 OK

```json
{
  "id": "uuid",
  "checklist": "uuid-checklist",
  "title": "آبیاری نهال‌های گلخانه شماره ۲",
  "is_completed": true,
  "completed_by": "uuid-کاربر",
  "completed_at": "2026-06-07T09:30:00+03:30",
  "description": "آبیاری کامل انجام شد."
}
```

---

## 10.5 حذف تسک

```
DELETE /api/tasks/{task_uuid}/
```

**دسترسی:** 👑 فقط ADMIN

---

---

# ⚠️ کدهای وضعیت HTTP

| کد | معنی | زمان وقوع |
|---|---|---|
| `200 OK` | موفق | GET، PUT، PATCH |
| `201 Created` | ایجاد شد | POST موفق |
| `204 No Content` | حذف شد | DELETE موفق |
| `400 Bad Request` | داده نامعتبر | فیلد اجباری خالی، validation error |
| `401 Unauthorized` | توکن ندارد یا منقضی شده | همه endpointهای محافظت‌شده |
| `403 Forbidden` | سطح دسترسی کافی نیست | USER به عملیات ADMIN |
| `404 Not Found` | رکورد پیدا نشد | UUID اشتباه |
| `500 Internal Server Error` | خطای سرور | — |

---

# 💡 نکات مهم فرانت‌اند

**جریان صحیح ثبت فاکتور فروش:**
ابتدا از `/api/customers/` مشتری را پیدا یا بسازید — سپس از `/api/sellers/` فروشنده را بگیرید — بعد فاکتور را با UUID هر دو ثبت کنید.

**مدیریت توکن:**
`access_token` را در متغیر JavaScript نگه دارید (نه `localStorage`) چون توکن دارای امضا است و فقط ۱۵ دقیقه معتبر است. از interceptor برای تمدید خودکار استفاده کنید.

**همه IDها UUID هستند:**
تمام `id`ها از نوع `UUID v4` (string) هستند.

**فیلدهای ⚙️ خودکار:**
هرگز `created_by`، `date_time`، `remaining_balance`، `total_price`، `completed_by`، `completed_at` را در Request ارسال نکنید — سرور آن‌ها را خودش محاسبه می‌کند.

**credentials در fetch:**
برای کار کردن صحیح کوکی `refresh_token`، همیشه `credentials: 'include'` را در تمام درخواست‌ها بگذارید.

**شماره چک یکتا:**
`cheque_number` در کل سیستم (هم فاکتور فروش، هم هزینه) یکتا است. تکرار آن `400 Bad Request` می‌دهد، مگر برای چک ظهرنویسی‌شده (`is_endorsed: true`).
