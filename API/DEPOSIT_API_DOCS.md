# 📦 مستندات API — سفارش‌های بیعانه (Deposit Orders)

> افزوده شده به RetailHub — نسخه ۳
> Base URL: `http://185.213.164.106/api/`

---

## معماری کلی

```
DepositOrder  ──────────────────────────────────────────────────
│  branch, created_by, seller, customer                        │
│  delivery_date                                               │
│  total_amount, discount_amount                               │
│  deposit_paid, remaining_debt  (خودکار)                     │
│  deposit_payment_method, debt_payment_method                 │
│  status: PENDING → DELIVERED / CANCELLED                     │
│  sale ──────────→ Sale (پس از تسویه نهایی)                  │
└──────────────────────────────────────────────────────────────┘
         │  1:N
         ▼
DepositOrderItem
│  item_name, quantity, unit_price, total_price (خودکار)
└──────────────────────────────────────────────────────────────
```

**فرمول محاسبه بدهی (خودکار در سرور):**
```
remaining_debt = total_amount - discount_amount - deposit_paid
```

---

## Endpoints

| متد | آدرس | توضیح | دسترسی |
|---|---|---|---|
| GET | `/api/deposit-orders/` | لیست سفارش‌ها | 🔐 همه |
| POST | `/api/deposit-orders/` | ثبت سفارش جدید | 🔐 همه |
| GET | `/api/deposit-orders/{uuid}/` | جزئیات کامل + اقلام | 🔐 همه |
| PUT | `/api/deposit-orders/{uuid}/` | ویرایش کامل | 📝 صاحب یا ADMIN |
| PATCH | `/api/deposit-orders/{uuid}/` | ویرایش جزئی | 📝 صاحب یا ADMIN |
| DELETE | `/api/deposit-orders/{uuid}/` | حذف | 📝 صاحب یا ADMIN |
| PATCH | `/api/deposit-orders/{uuid}/settle/` | تسویه نهایی | 📝 صاحب یا ADMIN |

---

## 1. لیست سفارش‌های بیعانه

```
GET /api/deposit-orders/
```

### Query Parameters — فیلتر اختیاری

| پارامتر | مثال | توضیح |
|---|---|---|
| `branch` | `شعبه پاسداران` | فیلتر شعبه |
| `status` | `PENDING` | وضعیت: `PENDING` / `DELIVERED` / `CANCELLED` |
| `seller` | `uuid` | UUID فروشنده |
| `customer` | `uuid` | UUID مشتری |
| `from_date` | `2026-06-01` | از تاریخ ثبت |
| `to_date` | `2026-06-30` | تا تاریخ ثبت |

### مثال

```
GET /api/deposit-orders/?status=PENDING&branch=شعبه پاسداران
```

### Response — 200 OK

```json
[
  {
    "id": "a1b2c3d4-...",
    "created_at": "2026-06-09T10:00:00+03:30",
    "branch": "شعبه پاسداران",
    "created_by": "cashier (صندوق‌دار)",
    "seller": "uuid-فروشنده",
    "seller_name": "امیر قاسمی",
    "customer": "uuid-مشتری",
    "customer_name": "علیرضا فتاحی",
    "customer_phone": "09154445566",
    "delivery_date": "2026-07-15",
    "total_amount": "8000000.00",
    "discount_amount": "500000.00",
    "deposit_paid": "2000000.00",
    "remaining_debt": "5500000.00",
    "status": "PENDING",
    "sale": null,
    "description": "سفارش نهال بید مجنون"
  }
]
```

> نتایج نزولی بر اساس `created_at` مرتب‌سازی می‌شوند.

---

## 2. ثبت سفارش بیعانه جدید

```
POST /api/deposit-orders/
```

### Request Body

```json
{
  "branch": "شعبه پاسداران",
  "seller": "uuid-فروشنده",
  "customer": "uuid-مشتری",
  "delivery_date": "2026-07-15",
  "total_amount": "8000000.00",
  "discount_amount": "500000.00",
  "deposit_paid": "2000000.00",
  "deposit_payment_method": "CASH",
  "description": "سفارش نهال بید مجنون — تحویل ۲۵ تیر",
  "items": [
    {
      "item_name": "نهال بید مجنون",
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

### فیلدها

| فیلد | نوع | اجباری | توضیح |
|---|---|---|---|
| `branch` | string | ✴️ | نام شعبه |
| `seller` | uuid | ✴️ | شناسه فروشنده |
| `customer` | uuid | ✴️ | شناسه مشتری (در بیعانه اجباری است) |
| `delivery_date` | date | ✴️ | تاریخ تحویل (YYYY-MM-DD) |
| `total_amount` | decimal | ✴️ | مبلغ کل سفارش |
| `discount_amount` | decimal | ◻️ | تخفیف — مبلغ ثابت (پیش‌فرض: ۰) |
| `deposit_paid` | decimal | ◻️ | مقدار بیعانه پرداخت‌شده (پیش‌فرض: ۰) |
| `deposit_payment_method` | string | ◻️ | `CASH` / `CARD_TO_CARD` / `CHEQUE` / `POS` / `OTHER` |
| `description` | string | ◻️ | توضیحات |
| `items` | array | ✴️ | حداقل ۱ قلم کالا |
| `items[].item_name` | string | ✴️ | نام کالا |
| `items[].quantity` | integer | ✴️ | تعداد |
| `items[].unit_price` | decimal | ✴️ | قیمت واحد |
| `remaining_debt` | — | ⚙️ | خودکار = total_amount - discount_amount - deposit_paid |
| `status` | — | ⚙️ | پیش‌فرض: `PENDING` |
| `created_by` | — | ⚙️ | خودکار از توکن |
| `created_at` | — | ⚙️ | خودکار |
| `sale` | — | ⚙️ | خودکار هنگام تسویه |

### Response — 201 Created

سفارش کامل با اقلام و `remaining_debt` محاسبه‌شده برگردانده می‌شود.

---

## 3. جزئیات سفارش خاص

```
GET /api/deposit-orders/{uuid}/
```

### Response — 200 OK

```json
{
  "id": "a1b2c3d4-...",
  "created_at": "2026-06-09T10:00:00+03:30",
  "branch": "شعبه پاسداران",
  "created_by": "cashier (صندوق‌دار)",
  "seller": "uuid-فروشنده",
  "seller_name": "امیر قاسمی",
  "customer": "uuid-مشتری",
  "customer_name": "علیرضا فتاحی",
  "customer_phone": "09154445566",
  "delivery_date": "2026-07-15",
  "total_amount": "8000000.00",
  "discount_amount": "500000.00",
  "deposit_paid": "2000000.00",
  "remaining_debt": "5500000.00",
  "deposit_payment_method": "CASH",
  "debt_payment_method": null,
  "status": "PENDING",
  "sale": null,
  "description": "سفارش نهال بید مجنون",
  "items": [
    {
      "id": "uuid",
      "item_name": "نهال بید مجنون",
      "quantity": 10,
      "unit_price": "600000.00",
      "total_price": "6000000.00"
    },
    {
      "id": "uuid",
      "item_name": "نهال کاج",
      "quantity": 5,
      "unit_price": "400000.00",
      "total_price": "2000000.00"
    }
  ]
}
```

---

## 4. ویرایش جزئی

```
PATCH /api/deposit-orders/{uuid}/
```

مثال — به‌روزرسانی تاریخ تحویل:

```json
{
  "delivery_date": "2026-07-20"
}
```

مثال — لغو سفارش:

```json
{
  "status": "CANCELLED"
}
```

> اگر `items` در PATCH ارسال شود، کل لیست اقلام جایگزین می‌شود.

---

## 5. تسویه نهایی — Settle

```
PATCH /api/deposit-orders/{uuid}/settle/
```

> وقتی مشتری بدهی رو کامل پرداخت کرد از این endpoint استفاده کنید.
>
> سرور به صورت اتمیک:
> - یک `Sale` جدید می‌سازد
> - بیعانه قبلی و بدهی را به عنوان `Payment` به Sale اضافه می‌کند
> - `DepositOrder.sale` را لینک می‌کند
> - وضعیت را `DELIVERED` می‌کند
> - آمار مشتری را به‌روز می‌کند

### Request Body

```json
{
  "debt_payment_method": "CASH",
  "description": "تسویه کامل — تحویل نهال‌ها انجام شد"
}
```

| فیلد | نوع | اجباری | مقادیر مجاز |
|---|---|---|---|
| `debt_payment_method` | string | ✴️ | `CASH` / `CARD_TO_CARD` / `CHEQUE` / `POS` / `COMBINED` / `OTHER` |
| `description` | string | ◻️ | توضیح فاکتور نهایی |

### Response — 200 OK

```json
{
  "message": "سفارش با موفقیت تسویه شد.",
  "sale_id": "f1e2d3c4-...",
  "deposit_order_id": "a1b2c3d4-..."
}
```

### خطاها

```json
// 400 — قبلاً تسویه شده
{ "error": "این سفارش قبلاً تسویه شده است." }

// 400 — لغو شده
{ "error": "سفارش لغو شده قابل تسویه نیست." }

// 400 — فیلد اجباری خالی
{ "error": "نحوه پرداخت بدهی (debt_payment_method) الزامی است." }
```

---

## نمونه کد JavaScript

```javascript
// ثبت سفارش بیعانه
const createDepositOrder = async (orderData) => {
  return await apiCall('http://185.213.164.106/api/deposit-orders/', {
    method: 'POST',
    body: JSON.stringify(orderData)
  });
};

// لیست بیعانه‌های در انتظار تحویل
const getPendingOrders = async () => {
  return await apiCall('http://185.213.164.106/api/deposit-orders/?status=PENDING');
};

// تسویه نهایی
const settleOrder = async (orderId, paymentMethod) => {
  return await apiCall(`http://185.213.164.106/api/deposit-orders/${orderId}/settle/`, {
    method: 'PATCH',
    body: JSON.stringify({ debt_payment_method: paymentMethod })
  });
};
```

---

## وضعیت‌های سفارش (Status Flow)

```
PENDING  ──→  DELIVERED  (از طریق /settle/)
   │
   └────→  CANCELLED   (از طریق PATCH با status: CANCELLED)
```

---

## نکات مهم

- **`customer` اجباری است** — برخلاف Sale معمولی، بیعانه همیشه به یک مشتری وابسته است.
- **`remaining_debt` خودکار است** — هرگز آن را ارسال نکنید.
- **`items` در PATCH جایگزین می‌شود** — اگر می‌خواهید اقلام را ویرایش کنید، لیست کامل جدید را ارسال کنید.
- **پس از تسویه، `sale_id` را ذخیره کنید** — برای مراجعه به فاکتور فروش نهایی.
- **ADMIN همه سفارش‌ها را می‌بیند** — سایر نقش‌ها فقط سفارش‌های خودشان را.
