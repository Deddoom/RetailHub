# 📖 مستندات کامل API — RetailHub
> ویژه برنامه‌نویسان فرانت‌اند (React / Vue / Flutter / iOS / Android)
> مجموع Endpointها: **56 endpoint**
> آخرین به‌روزرسانی: نسخه ۲

---

## 🌐 Base URL

```
http://185.213.164.106:8000/api/
```

---

## 🔑 احراز هویت

### مکانیزم کلی

سیستم از **Stateless Token** مبتنی بر امضای دیجیتال استفاده می‌کند:

| توکن | مدت اعتبار | محل ذخیره |
|---|---|---|
| Access Token | ۵ سال | `localStorage` یا حافظه جاوااسکریپت |

> چون توکن long-lived است، دیگه نیازی به refresh flow نیست. کاربر تا وقتی حسابش فعال باشه، لاگین می‌مونه.

### هدر الزامی برای تمام درخواست‌ها (به جز Login)

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
| ◻️ | فیلد اختیاری |

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
| `access_token` | توکن دسترسی ۵ ساله — در هدر Authorization استفاده کنید |
| `role` | نقش کاربر: `ADMIN` / `CASHIER` / `USER` |
| `branch` | شعبه کاربر — برای نمایش در UI |

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
    body: JSON.stringify({ username, password })
  });
  const data = await res.json();
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('role', data.role);
  localStorage.setItem('branch', data.branch);
  return data;
};

const apiCall = async (url, options = {}) => {
  const token = localStorage.getItem('access_token');
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...options.headers
    }
  });
  return res.json();
};

const logout = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('role');
  localStorage.removeItem('branch');
  window.location.href = '/login';
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
| `branch` | string | ◻️ | نام شعبه |
| `is_active` | boolean | ◻️ | پیش‌فرض: `true` |

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

> ⚠️ **تنها راه قطع دسترسی یک کاربر، غیرفعال کردن حساب او از طریق همین endpoint است.** سیستم در هر درخواست وضعیت `is_active` را مستقیماً از دیتابیس چک می‌کند.

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

## 3.1 لیست فروشندگان (کامل)

```
GET /api/sellers/
```

**دسترسی:** 🔐 همه کاربران احراز هویت‌شده

### Response — 200 OK

```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "امیر قاسمی",
    "phone": "09120001122",
    "branch": "شعبه پاسداران"
  }
]
```

---

## 3.2 لیست ساده فروشندگان برای Dropdown — **[جدید]**

```
GET /api/sellers/lookup/
```

**دسترسی:** 🔐 همه کاربران احراز هویت‌شده

> این endpoint ویژه پر کردن **dropdown** در فرم ثبت فاکتور طراحی شده است.
> فقط فیلدهای ضروری (UUID، نام، شماره، شعبه) برمی‌گرداند.

### Response — 200 OK

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "امیر قاسمی",
    "phone": "09120001122",
    "branch": "شعبه پاسداران"
  },
  {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "name": "سارا احمدی",
    "phone": "09131112233",
    "branch": "شعبه ولیعصر"
  }
]
```

### نمونه استفاده در فرانت‌اند

```javascript
// پر کردن dropdown فروشندگان قبل از ثبت فاکتور
const loadSellers = async () => {
  const sellers = await apiCall('http://185.213.164.106/api/sellers/lookup/');
  // sellers[0].id → UUID برای ارسال در فاکتور
  // sellers[0].name → نمایش در dropdown
  return sellers;
};
```

---

## 3.3 ثبت فروشنده جدید

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
| `phone` | string | ◻️ | شماره موبایل (یکتا) |
| `branch` | string | ✴️ | نام شعبه |

---

## 3.4 مشاهده فروشنده خاص

```
GET /api/sellers/{seller_uuid}/
```

**دسترسی:** 🔐 همه

---

## 3.5 ویرایش فروشنده

```
PUT   /api/sellers/{seller_uuid}/
PATCH /api/sellers/{seller_uuid}/
```

**دسترسی:** 👑 فقط ADMIN

---

## 3.6 حذف فروشنده

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
| `address` | string | ◻️ | — |
| `primary_goods` | string | ◻️ | `APARTMENT` / `OUTDOOR` / `FERTILIZER` / `NEHAL` / `POT` / `OTHER` |
| `buying_for` | string | ◻️ | `GARDEN` / `HOUSE` / `SHOP` / `OTHER` |
| `description` | string | ◻️ | — |

> فیلدهای `last_purchase_date`، `total_purchase_amount`، `last_purchase_type` **خودکار** هنگام ثبت فاکتور فروش به‌روز می‌شوند.

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

## 5.1 لیست فروش‌ها — **[بهبود یافته]**

```
GET /api/sales/
```

این endpoint لیست کامل فروش‌های ثبت‌شده را به صورت مختصر برمی‌گرداند.
ADMIN همه فاکتورها را می‌بیند، سایر نقش‌ها فقط فاکتورهای خودشان را.

### Query Parameters — فیلتر اختیاری

| پارامتر | نوع | مثال | توضیح |
|---|---|---|---|
| `branch` | string | `شعبه پاسداران` | فیلتر بر اساس شعبه |
| `seller` | uuid | `a1b2c3...` | فیلتر بر اساس UUID فروشنده |
| `customer` | uuid | `d4e5f6...` | فیلتر بر اساس UUID مشتری |
| `from_date` | date | `2026-06-01` | از تاریخ (YYYY-MM-DD) |
| `to_date` | date | `2026-06-30` | تا تاریخ (YYYY-MM-DD) |

### مثال با فیلتر

```
GET /api/sales/?branch=شعبه پاسداران&from_date=2026-06-01&to_date=2026-06-30
GET /api/sales/?seller=a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Response — 200 OK

```json
[
  {
    "id": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
    "date_time": "2026-06-07T10:30:00+03:30",
    "total_amount": "5500000.00",
    "remaining_balance": "0.00",
    "branch": "شعبه پاسداران",
    "description": "فروش نهال",
    "seller": "a1b2c3d4-...",
    "seller_name": "امیر قاسمی",
    "customer": "d4e5f6a7-...",
    "customer_name": "علیرضا فتاحی",
    "customer_phone": "09154445566",
    "created_by": "cashier (صندوق‌دار)"
  },
  {
    "id": "c1b2a3f4-...",
    "date_time": "2026-06-08T09:00:00+03:30",
    "total_amount": "1200000.00",
    "remaining_balance": "200000.00",
    "branch": "شعبه پاسداران",
    "description": "فروش گلدان — بدون مشتری",
    "seller": "a1b2c3d4-...",
    "seller_name": "امیر قاسمی",
    "customer": null,
    "customer_name": null,
    "customer_phone": null,
    "created_by": "cashier (صندوق‌دار)"
  }
]
```

> نتایج به صورت **نزولی بر اساس تاریخ** (`-date_time`) مرتب‌سازی می‌شوند.

---

## 5.2 ثبت فاکتور فروش جدید

```
POST /api/sales/
```

> **تغییر مهم:** فیلد `customer` حالا **اختیاری** است.
> می‌توانید فاکتور را بدون مشتری ثبت کنید — مثلاً برای فروش‌های نقدی سریع.

### Request Body — ساده‌ترین حالت بدون مشتری **[جدید]**

```json
{
  "total_amount": "2000000.00",
  "branch": "شعبه پاسداران",
  "seller": "uuid-فروشنده",
  "description": "فروش گلدان — مشتری ناشناس",
  "payments": [
    {
      "payment_method": "CASH",
      "amount": "2000000.00",
      "description": "پرداخت نقدی کامل"
    }
  ]
}
```

### Request Body — با مشتری و پرداخت نقدی

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
          "cheque_image_url": "https://storage.retailhub.com/cheques/chq-001.jpg",
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
| `customer` | uuid | ◻️ | شناسه مشتری — **اختیاری** |
| `description` | string | ◻️ | توضیح فاکتور |
| `payments` | array | ◻️ | لیست پرداخت‌ها |
| `deposit_items` | array | ◻️ | اقلام بیعانه (اجباری اگر payment_method=DEPOSIT) |
| `remaining_balance` | decimal | ⚙️ | خودکار = total_amount - sum(payments) |
| `date_time` | datetime | ⚙️ | خودکار |
| `created_by` | string | ⚙️ | خودکار از توکن |

### فیلدهای Payment (داخل payments[])

| فیلد | نوع | اجباری | مقادیر مجاز |
|---|---|---|---|
| `payment_method` | string | ✴️ | `CASH` / `CARD_TO_CARD` / `SHEBA` / `POS` / `COMBINED` / `REMAINING` / `DEPOSIT` / `CHEQUE` |
| `amount` | decimal | ✴️ | مبلغ این پرداخت |
| `description` | string | ◻️ | توضیح |
| `cheques` | array | ◻️ | فقط برای `CHEQUE` و `COMBINED` |

### فیلدهای Cheque (داخل payments[].cheques[]) — **[به‌روز شده]**

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `cheque_number` | string | ✴️ | شماره چک (یکتا در کل سیستم) |
| `due_date` | date | ✴️ | تاریخ سررسید (YYYY-MM-DD) |
| `amount` | decimal | ✴️ | مبلغ چک |
| `customer_phone` | string | ◻️ | پیش‌فرض: شماره مشتری فاکتور |
| `customer_name` | string | ◻️ | پیش‌فرض: نام مشتری فاکتور |
| `cheque_image_url` | string | ◻️ | لینک عکس چک — **اختیاری** |
| `description` | string | ◻️ | — |

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
- اگر `customer` ارسال نشود یا `null` باشد، به‌روزرسانی آمار مشتری انجام نمی‌شود

### Response — 201 Created

فاکتور کامل با تمام nested objectها برگردانده می‌شود.

---

## 5.3 مشاهده فاکتور خاص (کامل با جزئیات)

```
GET /api/sales/{sale_uuid}/
```

### Response — 200 OK

```json
{
  "id": "uuid",
  "total_amount": "5500000.00",
  "remaining_balance": "0.00",
  "date_time": "2026-06-07T10:30:00+03:30",
  "branch": "شعبه پاسداران",
  "seller": { "id": "uuid", "name": "امیر قاسمی", "phone": "...", "branch": "..." },
  "customer": { "id": "uuid", "name": "علیرضا فتاحی", "phone": "..." },
  "created_by": "admin (مدیر سیستم)",
  "description": "فروش نهال",
  "payments": [
    {
      "id": "uuid",
      "payment_method": "CHEQUE",
      "amount": "3000000.00",
      "description": "چک صیادی بانک ملی",
      "cheques": [
        {
          "id": "uuid",
          "cheque_number": "1234/5678-Melli",
          "due_date": "2026-08-20",
          "amount": "3000000.00",
          "customer_name": "علیرضا فتاحی",
          "customer_phone": "09154445566",
          "cheque_image_url": "https://storage.retailhub.com/cheques/chq-001.jpg",
          "is_endorsed": false,
          "description": "چک ثبت شده در سامانه صیاد"
        }
      ]
    }
  ],
  "deposit_items": [
    {
      "id": "uuid",
      "item_name": "گلدان سفالی بزرگ درجه ۱",
      "quantity": 10,
      "unit_price": "250000.00",
      "total_price": "2500000.00"
    }
  ]
}
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
    "cheques": [
      {
        "id": "uuid",
        "cheque_number": "9999/1111-Saderat",
        "due_date": "2026-09-01",
        "amount": "1500000.00",
        "is_endorsed": false,
        "cheque_image_url": "https://storage.retailhub.com/cheques/chq-002.jpg",
        "description": "چک بابت خرید کود"
      }
    ]
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

### Request Body — هزینه با چک جدید + عکس چک

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
      "cheque_image_url": "https://storage.retailhub.com/cheques/chq-003.jpg",
      "description": "چک جدید بابت خرید"
    }
  ]
}
```

### Request Body — خرج کردن چک دریافتی (ظهرنویسی) + عکس اختیاری

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
      "cheque_image_url": "https://storage.retailhub.com/cheques/chq-001-endorsed.jpg",
      "description": "چک دریافتی از فتاحی — ظهرنویسی شده"
    }
  ]
}
```

> وقتی `is_endorsed: true` باشد، سیستم چک را در دیتابیس پیدا کرده و وضعیتش را به «خرج‌شده» تغییر می‌دهد.
> اگر `cheque_image_url` همراه چک endorsed ارسال شود، عکس هم آپدیت می‌شود.

### فیلدهای Expense

| فیلد | نوع | اجباری | مقادیر مجاز |
|---|---|---|---|
| `amount` | decimal | ✴️ | مبلغ هزینه |
| `payment_method` | string | ✴️ | `CASH` / `CARD` / `ACCOUNT_TO_ACCOUNT` / `COMBINED` / `CHEQUE` |
| `date` | date | ✴️ | YYYY-MM-DD |
| `category` | string | ✴️ | دسته‌بندی هزینه |
| `branch` | string | ✴️ | نام شعبه |
| `invoice_image_url` | string | ◻️ | لینک عکس فاکتور |
| `description` | string | ◻️ | توضیح |
| `cheques` | array | ◻️ | فقط برای `CHEQUE` و `COMBINED` |
| `created_by` | string | ⚙️ | خودکار از توکن |

### فیلدهای Cheque در هزینه — **[به‌روز شده]**

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `cheque_number` | string | ✴️ | شماره چک |
| `due_date` | date | ✴️ | تاریخ سررسید |
| `amount` | decimal | ✴️ | مبلغ چک |
| `is_endorsed` | boolean | ✴️ | `false` = چک جدید / `true` = ظهرنویسی چک قبلی |
| `cheque_image_url` | string | ◻️ | لینک عکس چک — **اختیاری** |
| `description` | string | ◻️ | توضیح |

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
| `description` | string | ◻️ | توضیح |
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

## 10.4 به‌روزرسانی وضعیت تسک

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

### Request Body — برای USER

```json
{
  "is_completed": true,
  "description": "آبیاری نهال‌های گلخانه شماره ۲ به طور کامل انجام شد."
}
```

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `is_completed` | boolean | ◻️ | `true` = انجام شد |
| `description` | string | ◻️ | گزارش انجام کار |
| `completed_by` | — | ⚙️ | خودکار — کاربری که `is_completed=true` زده |
| `completed_at` | — | ⚙️ | خودکار — زمان تکمیل |

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

# ۱۱. شعب سیستم (Branches)

> جدید در نسخه ۳
> سیستم اکنون از ۴ شعبه ثابت پشتیبانی می‌کند و فرانت‌اند نباید لیست شعب را HardCode کند.

---

## 11.1 دریافت لیست شعب

```http
GET /api/branches/
```

**دسترسی:** 🔐 همه کاربران احراز هویت‌شده

### Header

```http
Authorization: Bearer <access_token>
```

### Response — 200 OK

```json
[
  {
    "value": "HEAD_OFFICE",
    "label": "دفتر مرکزی"
  },
  {
    "value": "BRANCH_1",
    "label": "شعبه ۱"
  },
  {
    "value": "BRANCH_2",
    "label": "شعبه ۲"
  },
  {
    "value": "BRANCH_3",
    "label": "شعبه ۳"
  }
]
```

### فیلدها

| فیلد  | نوع    | توضیح                         |
| ----- | ------ | ----------------------------- |
| value | string | مقدار ذخیره‌شده در دیتابیس    |
| label | string | متن قابل نمایش در رابط کاربری |

### کاربرد در فرانت‌اند

* فرم ثبت فاکتور فروش
* فرم ثبت سفارش بیعانه
* فرم ثبت هزینه
* فرم ثبت خرابی
* فرم خروج کالا
* فیلتر گزارش‌ها
* نمایش شعبه کاربر

---

# ۱۲. سفارش‌های بیعانه (Deposit Orders)

> جدید در نسخه ۳

**دسترسی:** 📝 ADMIN همه سفارش‌ها را مشاهده می‌کند. سایر کاربران فقط سفارش‌های ثبت‌شده توسط خودشان را مشاهده می‌کنند.

---

## ساختار کلی

```
DepositOrder
 ├── Customer
 ├── Seller
 ├── Branch
 ├── DepositOrderItems[]
 └── Sale (پس از تسویه)
```

---

## وضعیت‌های سفارش

| مقدار     | توضیح           |
| --------- | --------------- |
| PENDING   | در انتظار تحویل |
| DELIVERED | تحویل شده       |
| CANCELLED | لغو شده         |

---

## فرمول محاسبه بدهی

```
remaining_debt =
total_amount
-
discount_amount
-
deposit_paid
```

این مقدار توسط سرور محاسبه می‌شود.

---

## 12.1 لیست سفارش‌های بیعانه

```http
GET /api/deposit-orders/
```

### Query Parameters

| پارامتر   | نوع        | توضیح         |
| --------- | ---------- | ------------- |
| branch    | string     | فیلتر شعبه    |
| status    | string     | فیلتر وضعیت   |
| seller    | uuid       | فیلتر فروشنده |
| customer  | uuid       | فیلتر مشتری   |
| from_date | YYYY-MM-DD | از تاریخ      |
| to_date   | YYYY-MM-DD | تا تاریخ      |

### مثال

```http
GET /api/deposit-orders/?status=PENDING
```

```http
GET /api/deposit-orders/?branch=HEAD_OFFICE
```

```http
GET /api/deposit-orders/?status=PENDING&branch=HEAD_OFFICE
```

### Response

```json
[
  {
    "id": "uuid",
    "created_at": "2026-06-10T10:00:00Z",

    "branch": "HEAD_OFFICE",

    "seller": "uuid",
    "seller_name": "امیر قاسمی",

    "customer": "uuid",
    "customer_name": "علیرضا فتاحی",
    "customer_phone": "09121234567",

    "delivery_date": "2026-07-15",

    "total_amount": "8000000.00",
    "discount_amount": "500000.00",

    "deposit_paid": "2000000.00",
    "remaining_debt": "5500000.00",

    "status": "PENDING",

    "sale": null,

    "description": "سفارش نهال"
  }
]
```

---

## 12.2 ثبت سفارش بیعانه جدید

```http
POST /api/deposit-orders/
```

### Request Body

```json
{
  "branch": "HEAD_OFFICE",

  "seller": "seller_uuid",

  "customer": "customer_uuid",

  "delivery_date": "2026-07-15",

  "total_amount": "8000000.00",

  "discount_amount": "500000.00",

  "deposit_paid": "2000000.00",

  "deposit_payment_method": "CASH",

  "description": "سفارش نهال",

  "items": [
    {
      "item_name": "نهال گردو",
      "quantity": 10,
      "unit_price": "600000.00"
    },
    {
      "item_name": "نهال کاج",
      "quantity": 5,
      "unit_price": "400000.00"
    }
  ]
}
```

### فیلدهای اصلی

| فیلد                   | نوع     | اجباری |
| ---------------------- | ------- | ------ |
| branch                 | string  | ✅      |
| seller                 | uuid    | ✅      |
| customer               | uuid    | ✅      |
| delivery_date          | date    | ✅      |
| total_amount           | decimal | ✅      |
| discount_amount        | decimal | ❌      |
| deposit_paid           | decimal | ❌      |
| deposit_payment_method | string  | ❌      |
| description            | string  | ❌      |
| items                  | array   | ✅      |

---

## مقادیر مجاز deposit_payment_method

```text
CASH
CARD_TO_CARD
CHEQUE
POS
OTHER
```

---

## فیلدهای items

| فیلد       | نوع     | اجباری |
| ---------- | ------- | ------ |
| item_name  | string  | ✅      |
| quantity   | integer | ✅      |
| unit_price | decimal | ✅      |

---

## 12.3 مشاهده سفارش خاص

```http
GET /api/deposit-orders/{uuid}/
```

### Response

```json
{
  "id": "uuid",

  "created_at": "2026-06-10T10:00:00Z",

  "branch": "HEAD_OFFICE",

  "seller": "seller_uuid",
  "seller_name": "امیر قاسمی",

  "customer": "customer_uuid",
  "customer_name": "علیرضا فتاحی",
  "customer_phone": "09121234567",

  "delivery_date": "2026-07-15",

  "total_amount": "8000000.00",

  "discount_amount": "500000.00",

  "deposit_paid": "2000000.00",

  "remaining_debt": "5500000.00",

  "deposit_payment_method": "CASH",

  "debt_payment_method": null,

  "status": "PENDING",

  "sale": null,

  "description": "سفارش نهال",

  "items": [
    {
      "id": "uuid",
      "item_name": "نهال گردو",
      "quantity": 10,
      "unit_price": "600000.00",
      "total_price": "6000000.00"
    }
  ]
}
```

---

## 12.4 ویرایش سفارش

```http
PUT /api/deposit-orders/{uuid}/
```

یا

```http
PATCH /api/deposit-orders/{uuid}/
```

### تغییر تاریخ تحویل

```json
{
  "delivery_date": "2026-07-20"
}
```

### لغو سفارش

```json
{
  "status": "CANCELLED"
}
```

### نکته مهم

اگر فیلد items در PATCH ارسال شود:

```json
{
  "items": [...]
}
```

کل لیست قبلی حذف و با لیست جدید جایگزین خواهد شد.

---

## 12.5 حذف سفارش

```http
DELETE /api/deposit-orders/{uuid}/
```

### Response

```http
204 No Content
```

---

## 12.6 تسویه نهایی سفارش

```http
PATCH /api/deposit-orders/{uuid}/settle/
```

### Request Body

```json
{
  "debt_payment_method": "CASH",
  "description": "تحویل کالا انجام شد"
}
```

### payment methods

```text
CASH
CARD_TO_CARD
CHEQUE
POS
COMBINED
OTHER
```

### Response

```json
{
  "message": "سفارش با موفقیت تسویه شد.",
  "sale_id": "sale_uuid",
  "deposit_order_id": "deposit_uuid"
}
```

### خطاها

```json
{
  "error": "این سفارش قبلاً تسویه شده است."
}
```

```json
{
  "error": "سفارش لغو شده قابل تسویه نیست."
}
```

```json
{
  "error": "نحوه پرداخت بدهی (debt_payment_method) الزامی است."
}
```

---

# راهنمای پیاده‌سازی فرانت‌اند

## صفحه ثبت بیعانه

ابتدا:

```http
GET /api/branches/
GET /api/sellers/lookup/
GET /api/customers/
```

سپس:

```http
POST /api/deposit-orders/
```

---

## صفحه لیست بیعانه‌ها

فیلترها:

* شعبه
* فروشنده
* مشتری
* وضعیت
* از تاریخ
* تا تاریخ

Endpoint:

```http
GET /api/deposit-orders/
```

---

## صفحه جزئیات

```http
GET /api/deposit-orders/{id}/
```

نمایش:

* اطلاعات مشتری
* اطلاعات فروشنده
* شعبه
* اقلام سفارش
* بیعانه پرداختی
* بدهی باقی‌مانده
* وضعیت سفارش

---

## صفحه تسویه

```http
PATCH /api/deposit-orders/{id}/settle/
```

بعد از موفقیت:

* بروزرسانی وضعیت به DELIVERED
* ذخیره sale_id
* هدایت به صفحه فاکتور فروش
* رفرش اطلاعات سفارش

---

## متد get برای شعب

```
import 'dart:convert';
import 'package:http/http.dart' as http;

Future<List<dynamic>> fetchBranches(String accessToken) async {
  final url = Uri.parse('http://185.213.164.106/api/branches/');
  
  try {
    final response = await http.get(
      url,
      headers: {
        'Content-Type': 'application/json; charset=UTF-8',
        'Authorization': 'Bearer $accessToken', // توکن دریافتی از لاگین
      },
    );

    if (response.statusCode == 200) {
      // رمزگشایی صحیح متون فارسی با utf8.decode
      List<dynamic> branches = jsonDecode(utf8.decode(response.bodyBytes));
      return branches;
    } else {
      print('خطا در دریافت شعب. کد وضعیت: ${response.statusCode}');
      throw Exception('Failed to load branches');
    }
  } catch (e) {
    print('خطا در ارتباط با سرور: $e');
    rethrow;
  }
}

```

## حذف فروشنده
## متد: DELETE

## آدرس: DELETE /api/sellers/{id}/

## کد Flutter
```
dartFuture<void> deleteSeller(String sellerId) async {
  final response = await dio.delete(
    '/api/sellers/$sellerId/',
  );

  // موفق: 204 No Content
  // خطا: 400 اگر فروشنده فاکتور داشته باشه
}
```
## هندل کردن جواب‌ها
## Status Codeمعنیکار فرانت‌اند204حذف موفقنمایش پیام موفقیت + رفرش لیست400رکورد وابسته داردنمایش پیام خطا به کاربر403دسترسی ندارد (غیر ادمین)نمایش پیام دسترسی404فروشنده پیدا نشدنمایش پیام خطا

## مثال کامل با مدیریت خطا
```
dartFuture<void> deleteSeller(String sellerId) async {
  try {
    await dio.delete('/api/sellers/$sellerId/');

    // ✅ حذف موفق
    showSnackBar('فروشنده با موفقیت حذف شد');
    fetchSellers(); // رفرش لیست

  } on DioException catch (e) {
    if (e.response?.statusCode == 400) {
      // ❌ رکورد وابسته دارد
      final message = e.response?.data['error'] ?? 'خطا در حذف فروشنده';
      showSnackBar(message); // "این رکورد دارای اطلاعات وابسته است و قابل حذف نمی‌باشد."

    } else if (e.response?.statusCode == 403) {
      showSnackBar('شما دسترسی حذف ندارید');

    } else if (e.response?.statusCode == 404) {
      showSnackBar('فروشنده یافت نشد');

    } else {
      showSnackBar('خطای سرور، لطفاً دوباره تلاش کنید');
    }
  }
}
```
## نکته مهم: چون در get_permissions فقط ادمین می‌تونه حذف کنه، مطمئن بشید توکن کاربر ادمین در هدر ارسال میشه:
```
dartdio.options.headers['Authorization'] = 'Bearer $token';
```






---

# تغییرات نسخه ۳

✅ اضافه شدن API شعب

✅ اضافه شدن Deposit Orders

✅ پشتیبانی کامل از ۴ شعبه

✅ امکان فیلتر بر اساس شعبه

✅ امکان تسویه خودکار و تولید Sale

✅ پشتیبانی از وضعیت‌های PENDING / DELIVERED / CANCELLED

✅ پشتیبانی از اقلام سفارش (items)

✅ محاسبه خودکار remaining_debt

✅ بروزرسانی آمار مشتری هنگام تسویه


# 💡 نکات مهم فرانت‌اند

**مدیریت توکن:**
توکن ۵ ساله است — نیازی به interceptor، refresh loop یا مدیریت کوکی نیست. بعد از Login توکن رو در `localStorage` ذخیره کنید.

**جریان صحیح ثبت فاکتور فروش:**
ابتدا از `GET /api/sellers/lookup/` لیست فروشندگان را بگیرید — در صورت نیاز از `/api/customers/` مشتری را پیدا یا بسازید — سپس فاکتور را ثبت کنید. `customer` اختیاری است.

**آپلود عکس چک:**
سیستم فقط **URL** عکس چک را ذخیره می‌کند. عکس را ابتدا روی سرویس ذخیره‌سازی خودتان آپلود کنید، سپس URL برگشتی را در فیلد `cheque_image_url` ارسال کنید.

**لیست فروش‌ها:**
از `GET /api/sales/` برای مشاهده همه فروش‌ها استفاده کنید. از query parameterها برای فیلتر کردن بر اساس شعبه، فروشنده، مشتری یا بازه تاریخی استفاده کنید.

**تنها راه logout:**
توکن رو از `localStorage` پاک کنید. هیچ endpoint ای برای logout لازم نیست.

**تنها راه قطع دسترسی کاربر:**
از `PATCH /api/users/{uuid}/` با `{"is_active": false}` حساب را غیرفعال کنید.

**همه IDها UUID هستند.**

**فیلدهای ⚙️ خودکار:**
هرگز `created_by`، `date_time`، `remaining_balance`، `total_price`، `completed_by`، `completed_at` را در Request ارسال نکنید.

**شماره چک یکتا:**
`cheque_number` در کل سیستم یکتا است — مگر برای ظهرنویسی (`is_endorsed: true`).



---

# مستندات تکمیلی و جامع API سیستم RetailHub

این مستند حاوی ساختار کامل اندپوینت‌ها، قوانین سطوح دسترسی مبتنی بر درختواره نقش‌ها، مأموریت‌ها، چک‌لیست‌ها و فرآیندهای مالی سیستم است.

---

## ── درختواره نقش‌ها و منطق سلسله‌مراتب (Role Hierarchy)

دسترسی‌ها و پایش اطلاعات در سیستم بر اساس ساختار درختی زیر ارزیابی می‌شود:
* **ADMIN**: دسترسی کامل به تمامی نقش‌ها و کل داده‌های سیستم.
* **FINANCIAL_MANAGER**: بالادستِ حسابدار، آمارگیر، صندوق‌دار و کارکنان عادی.
* **EXECUTIVE_MANAGER**: بالادستِ سرپرست و کارکنان عادی.
* **SUPERVISOR**: بالادستِ کارکنان عادی (USER).
* **ACCOUNTANT**: بالادستِ صندوق‌دار و کارکنان عادی.

> **قانون پایش:** کاربران بالادست به مأموریت‌ها، چک‌لیست‌ها و عملکرد تمام کاربران زیرمجموعه خود به صورت تجمیعی دسترسی نظارتی دارند.

---

## ── ۱. احراز هویت و مدیریت کاربران

### ورود به سیستم (Login)
* **آدرس:** `POST /api/auth/token/`
* **دسترسی:** عمومی (`AllowAny`)

```json
{
  "username": "amir_admin",
  "password": "secret_password"
}
```

**پاسخ موفق (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "roles": ["ADMIN"],
  "branch": "شعبه بهشتی"
}
```

### مدیریت کاربران (Users)

* **آدرس:** `/api/users/`
* **متدها:** `GET, POST, PUT, PATCH, DELETE`
* **دسترسی:** فقط ADMIN یا Superuser

```json
{
  "username": "employee_1",
  "password": "secure_password",
  "branch": "شعبه مدرس",
  "role_ids": ["uuid-of-role-cashier"],
  "is_active": true
}
```

---

## ── ۲. مأموریت‌ها (Missions)

* **آدرس مبدا:** `/api/missions/`
* **دسترسی:** کاربران احراز هویت شده (بر اساس شرط بالادستی)
* **جستجو:** `?search=` روی `title` و `description`

### ایجاد مأموریت جدید

```json
{
  "title": "سرکشی و بررسی انبار شعبه مدرس",
  "assigned_to": "uuid-of-target-user",
  "start_date": "2026-06-20T09:00:00Z",
  "end_date": "2026-06-20T17:00:00Z",
  "status": "PENDING",
  "description": "بررسی موجودی فیزیکی گلدان‌ها و تطابق با سیستم"
}
```

**مقادیر مجاز وضعیت:**

```text
PENDING
DOING
COMPLETED
CANCELLED
```

---

## ── ۳. چک‌لیست‌ها و تسک‌ها (Checklists & Tasks)

### ایجاد چک‌لیست

```json
{
  "title": "کارهای شروع شیفت صبح صندوق",
  "frequency": "DAILY",
  "assigned_to": "uuid-of-cashier",
  "tasks": [
    {
      "title": "روشن کردن سیستم پوز و کارتخوان",
      "description": "بررسی اتصال کابل شبکه"
    },
    {
      "title": "شمارش پول نقد تنخواه اولیه",
      "description": "ثبت مبلغ در دفترچه"
    }
  ]
}
```

**مقادیر مجاز frequency:**

```text
DAILY
WEEKLY
MONTHLY
```

### منطق تکمیل تسک

با ارسال:

```json
{
  "is_completed": true
}
```

فیلدهای `completed_by` و `completed_at` به‌صورت خودکار مقداردهی می‌شوند.

---

## ── ۴. فرآیند فروش و تسویه بیعانه‌ها (Sales & Deposits)

### ثبت فروش

```json
{
  "total_amount": "5500000.00",
  "branch": "شعبه بهشتی",
  "seller": "uuid-of-seller",
  "customer": "uuid-of-customer",
  "description": "فروش گلدان و کود آپارتمانی",
  "payments": [
    {
      "payment_method": "CHEQUE",
      "amount": "3000000.00"
    },
    {
      "payment_method": "POS",
      "amount": "2500000.00"
    }
  ]
}
```

### تسویه سفارش بیعانه

`PATCH /api/deposit-orders/{id}/settle/`

```json
{
  "debt_payment_method": "POS",
  "description": "تسویه فاکتور و تحویل نهایی گیاه به مشتری"
}
```

```json
{
  "message": "سفارش با موفقیت تسویه شد.",
  "sale_id": "uuid-of-new-generated-sale",
  "deposit_order_id": "uuid-of-order"
}
```

---

## ── ۵. هزینه‌ها، ضایعات و خروج کالا

### گزارش ضایعات

```json
{
  "item_name": "گلدان سفالی سایز بزرگ (شکستگی شیفت شب)",
  "quantity": 3,
  "estimated_loss": "450000.00",
  "date": "2026-06-19",
  "branch": "شعبه کاجستان",
  "description": "در حین جابجایی کالاها آسیب دیده است."
}
```

### دلایل مجاز خروج کالا

```text
RETURN
DAMAGE
INTERNAL
```

---

## ── ۶. اطلاعات ثابت سیستم (Utilities)

### لیست شعب فعال

`GET /api/branches/`

```json
[
  { "value": "شعبه بهشتی", "label": "شعبه بهشتی" },
  { "value": "شعبه مدرس", "label": "شعبه مدرس" },
  { "value": "شعبه سپیده", "label": "شعبه سپیده" },
  { "value": "شعبه کاجستان", "label": "شعبه کاجستان" }
]
```

---

این مستندات جدید با کدهای فعلی بک‌اند سیستم شما هماهنگ است و برای توسعه‌دهندگان فرانت‌اند یا وب‌هوک‌ها به عنوان مرجع کاملاً دقیق عمل می‌کند.
