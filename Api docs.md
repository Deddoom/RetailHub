# 📖 مستندات فنی API سامانه RetailHub

این سند برای راهنمایی برنامه‌نویسان فرانت‌اند (React, Vue, Flutter, iOS, Android) جهت اتصال به APIهای سامانه RetailHub تهیه شده است.

---

# 🌐 Base URL

تمام درخواست‌ها باید با آدرس پایه زیر ارسال شوند:

```text
http://185.213.164.106:8000/api/
```

---

# 🔑 مکانیزم احراز هویت (Authentication Flow)

احراز هویت در این سیستم به صورت Stateless و مبتنی بر JWT انجام می‌شود.

* Access Token (مدت اعتبار: 15 دقیقه)
* Refresh Token (مدت اعتبار: 7 روز)

برای تمامی درخواست‌ها به جز Login و Refresh Token باید هدر زیر ارسال شود:

```http
Authorization: Bearer <Your_Access_Token>
```

---

# 🛣️ مسیرهای احراز هویت (Auth Endpoints)

## 1. ورود به سیستم (Login)

**URL**

```http
POST http://185.213.164.106:8000/api/auth/token/
```

**دسترسی:** عمومی (AllowAny)

### Request

```json
{
  "username": "admin",
  "password": "admin1234"
}
```

### Response

```json
{
  "access_token": "ey...[Base64_Encoded_Sign]",
  "role": "ADMIN",
  "branch": "دفتر مرکزی"
}
```

> یک کوکی HttpOnly به نام refresh_token نیز روی مرورگر ذخیره می‌شود.

---

## 2. تمدید توکن (Refresh Token)

**URL**

```http
POST http://185.213.164.106:8000/api/auth/token/refresh/
```

**دسترسی:** عمومی (AllowAny)

### Request

```json
{
  "refresh_token": "ey...[Base64_Encoded_Sign]"
}
```

### Response

```json
{
  "access_token": "ey...[New_Access_Token]"
}
```

---

# 💼 فاکتورهای فروش و پرداخت‌ها (Sales)

## لیست فاکتورها

```http
GET http://185.213.164.106:8000/api/sales/
```

## ثبت فاکتور جدید

```http
POST http://185.213.164.106:8000/api/sales/
```

### نمونه درخواست

```json
{
  "total_amount": "5500000.00",
  "branch": "شعبه پاسداران",
  "seller": "UUID-id-فروشنده",
  "customer": "UUID-id-مشتری",
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

### مدیریت یک فاکتور خاص

```http
GET    http://185.213.164.106:8000/api/sales/<sale_uuid_id>/
PUT    http://185.213.164.106:8000/api/sales/<sale_uuid_id>/
PATCH  http://185.213.164.106:8000/api/sales/<sale_uuid_id>/
DELETE http://185.213.164.106:8000/api/sales/<sale_uuid_id>/
```

---

# 👥 مشتریان (Customers)

## لیست مشتریان

```http
GET http://185.213.164.106:8000/api/customers/
```

## ثبت مشتری

```http
POST http://185.213.164.106:8000/api/customers/
```

## مدیریت مشتری

```http
GET    http://185.213.164.106:8000/api/customers/<customer_uuid_id>/
PUT    http://185.213.164.106:8000/api/customers/<customer_uuid_id>/
PATCH  http://185.213.164.106:8000/api/customers/<customer_uuid_id>/
DELETE http://185.213.164.106:8000/api/customers/<customer_uuid_id>/
```

---

# 👨‍💼 فروشندگان (Sellers)

## لیست فروشندگان

```http
GET http://185.213.164.106:8000/api/sellers/
```

## ثبت فروشنده

```http
POST http://185.213.164.106:8000/api/sellers/
```

## مدیریت فروشنده

```http
GET    http://185.213.164.106:8000/api/sellers/<seller_uuid_id>/
PUT    http://185.213.164.106:8000/api/sellers/<seller_uuid_id>/
PATCH  http://185.213.164.106:8000/api/sellers/<seller_uuid_id>/
DELETE http://185.213.164.106:8000/api/sellers/<seller_uuid_id>/
```

---

# 🧾 هزینه‌ها (Expenses)

## لیست هزینه‌ها

```http
GET http://185.213.164.106:8000/api/expenses/
```

## ثبت هزینه

```http
POST http://185.213.164.106:8000/api/expenses/
```

### نمونه درخواست

```json
{
  "amount": "1500000.00",
  "payment_method": "CHEQUE",
  "date": "2026-06-05",
  "category": "خرید سموم کشاورزی",
  "branch": "شعبه پاسداران",
  "invoice_image_url": "https://storage.retailhub.com/invoices/inv-908.png",
  "description": "خرید کود مایع و سم قارچ‌کش",
  "cheques": [
    {
      "cheque_number": "1234/5678-Melli",
      "is_endorsed": true,
      "due_date": "2026-08-20",
      "amount": "3000000.00"
    }
  ]
}
```

## مدیریت هزینه

```http
GET    http://185.213.164.106:8000/api/expenses/<expense_uuid_id>/
PUT    http://185.213.164.106:8000/api/expenses/<expense_uuid_id>/
PATCH  http://185.213.164.106:8000/api/expenses/<expense_uuid_id>/
DELETE http://185.213.164.106:8000/api/expenses/<expense_uuid_id>/
```

---

# 📉 گزارش خرابی (Damage Reports)

```http
GET  http://185.213.164.106:8000/api/damage-reports/
POST http://185.213.164.106:8000/api/damage-reports/
```

```http
GET    http://185.213.164.106:8000/api/damage-reports/<report_uuid_id>/
PUT    http://185.213.164.106:8000/api/damage-reports/<report_uuid_id>/
PATCH  http://185.213.164.106:8000/api/damage-reports/<report_uuid_id>/
DELETE http://185.213.164.106:8000/api/damage-reports/<report_uuid_id>/
```

---

# 📦 خروج کالا (Item Exits)

```http
GET  http://185.213.164.106:8000/api/item-exits/
POST http://185.213.164.106:8000/api/item-exits/
```

```http
GET    http://185.213.164.106:8000/api/item-exits/<exit_uuid_id>/
PUT    http://185.213.164.106:8000/api/item-exits/<exit_uuid_id>/
PATCH  http://185.213.164.106:8000/api/item-exits/<exit_uuid_id>/
DELETE http://185.213.164.106:8000/api/item-exits/<exit_uuid_id>/
```

---

# ✅ چک‌لیست‌ها (Checklists)

```http
GET  http://185.213.164.106:8000/api/checklists/
POST http://185.213.164.106:8000/api/checklists/
```

```http
GET    http://185.213.164.106:8000/api/checklists/<checklist_uuid_id>/
PUT    http://185.213.164.106:8000/api/checklists/<checklist_uuid_id>/
PATCH  http://185.213.164.106:8000/api/checklists/<checklist_uuid_id>/
DELETE http://185.213.164.106:8000/api/checklists/<checklist_uuid_id>/
```

---

# 📋 کارهای روزانه (Tasks)

```http
PUT   http://185.213.164.106:8000/api/tasks/<task_uuid_id>/
PATCH http://185.213.164.106:8000/api/tasks/<task_uuid_id>/
```

### نمونه درخواست

```json
{
  "is_completed": true,
  "description": "آبیاری نهال‌های گلخانه شماره ۲ به طور کامل انجام شد."
}
```

---

# 👤 کاربران سیستم (Users)

> فقط ADMIN

```http
GET  http://185.213.164.106:8000/api/users/
POST http://185.213.164.106:8000/api/users/
```

```http
GET    http://185.213.164.106:8000/api/users/<user_uuid_id>/
PUT    http://185.213.164.106:8000/api/users/<user_uuid_id>/
PATCH  http://185.213.164.106:8000/api/users/<user_uuid_id>/
DELETE http://185.213.164.106:8000/api/users/<user_uuid_id>/
```

---

# ⚠️ کدهای وضعیت متداول

| Status Code               | Description                      |
| ------------------------- | -------------------------------- |
| 200 OK                    | درخواست با موفقیت انجام شد       |
| 201 Created               | رکورد جدید ایجاد شد              |
| 400 Bad Request           | داده‌های ارسالی نامعتبر هستند    |
| 401 Unauthorized          | توکن ارسال نشده یا منقضی شده است |
| 403 Forbidden             | دسترسی کافی وجود ندارد           |
| 500 Internal Server Error | خطای داخلی سرور                  |

---

# 💡 نکات مهم برای فرانت‌اند

* قبل از ثبت فاکتور فروش، شناسه مشتری (Customer UUID) را از API مشتریان دریافت کنید.
* قبل از ثبت فاکتور فروش، شناسه فروشنده (Seller UUID) را از API فروشندگان دریافت کنید.
* تمامی شناسه‌ها از نوع UUID هستند.
* Access Token را در هدر Authorization ارسال کنید.
* Refresh Token برای تمدید نشست کاربر استفاده می‌شود.
* تمام Endpointهای فوق نیازمند احراز هویت هستند، به جز Login و Refresh Token.
