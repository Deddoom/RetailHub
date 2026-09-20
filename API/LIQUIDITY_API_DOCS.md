# 💵 مستندات فنی API ماژول «مدیریت نقدینگی» (Cash Flow & Liquidity Management)

این مستند، راهنمای جامع اتصال و استفاده از APIهای بخش **مدیریت نقدینگی** سامانه RetailHub برای تیم‌های توسعه فرانت‌اند (وب، موبایل و ...) می‌باشد.

---

## 🧭 پیش‌نیازها و احراز هویت

- **Base URL:**
  ```text
  /api/liquidity/
  ```
- **هدر احراز هویت (Authorization):**
  ```http
  Authorization: Bearer <access_token>
  ```
- **نقش‌های مجاز:**
  - ویرایش و ایجاد (`POST`, `PUT`, `DELETE`): نقش **مدیر مالی (`FINANCIAL_MANAGER`)** یا **ادمین کل (`ADMIN`)**.
  - مشاهده (`GET`): علاوه بر مدیر مالی و ادمین، مدیران اجرایی، حسابداران و سرپرستان نیز دسترسی دارند.

---

## 🧮 موتور محاسبه وضعیت هوشمند هزینه‌ها (Status Engine)

وضعیت هر هزینه به صورت لحظه‌ای با توجه به متغیرهای زیر محاسبه می‌شود:
- **بدهی باقی‌مانده:** `remaining_debt = amount - allocated_amount`
- **روزهای باقی‌مانده تا سررسید:** `days_remaining = due_date - today`
- **درآمد روزانه:** `daily_revenue` (تنظیم شده در سامانه)

### کدهای وضعیت و مفهوم آن‌ها:
| کد وضعیت | عنوان فارسی | شرط وقوع |
| :--- | :--- | :--- |
| `PAID` | پرداخت شده | هزینه تسویه نهایی شده و تایید پرداخت آن ثبت شده است (`is_paid = true`). |
| `EXCELLENT` | عالی | قبل از سررسید، کل مبلغ هزینه به طور کامل تامین و ذخیره شده است (`allocated >= amount`). |
| `OVERDUE` | عقب مانده | تاریخ سررسید گذشته است اما هزینه پرداخت نهایی نشده است. |
| `NORMAL` | عادی | نسبت نرخ ذخیره روزانه به درآمد روزانه کمتر از ۵۰٪ است ($Ratio < 0.50$). |
| `WARNING` | هشدار | نرخ ذخیره روزانه بین ۵۰٪ تا ۷۵٪ درآمد روزانه است ($0.50 \le Ratio \le 0.75$). |
| `CRITICAL` | خطرناک | نرخ ذخیره روزانه بالاتر از ۷۵٪ درآمد روزانه است ($Ratio > 0.75$). |

---

## 1️⃣ درآمد روزانه (Daily Revenue API)

یک تک‌مقدار که مبنای تعیین وضعیت‌های عادی، هشدار و خطرناک هزینه‌ها است.

### 1.1. دریافت مبلغ درآمد روزانه فعلی
- **متد:** `GET`
- **آدرس:** `/api/liquidity/daily-revenue/`
- **نمونه پاسخ:**
```json
{
  "id": 1,
  "amount": "50000000.00",
  "updated_by": 2,
  "updated_by_name": "امیر رضایی",
  "updated_at": "2026-09-20T22:30:00Z"
}
```

### 1.2. تغییر / به‌روزرسانی درآمد روزانه
- **متد:** `POST` یا `PUT`
- **آدرس:** `/api/liquidity/daily-revenue/`
- **بدنه درخواست:**
```json
{
  "amount": 60000000
}
```
- **پاسخ:** اطلاعات به‌روزشده با وضعیت `200 OK`.

---

## 2️⃣ کارت‌های سه‌گانه نقدینگی (Cards API)

### 2.1. مشاهده خلاصه همزمان هر سه کارت
- **متد:** `GET`
- **آدرس:** `/api/liquidity/cards/` (یا `/api/liquidity/cards/overview/`)
- **نمونه پاسخ:**
```json
{
  "expense_card": {
    "title": "کارت هزینه‌ها",
    "total_allocated": 115000000.0,
    "total_target": 230000000.0,
    "remaining_needed": 115000000.0,
    "active_expenses_count": 2,
    "description": "جمع مقادیر داده شده برای تمامی هزینه‌های پرداخت‌نشده جاری"
  },
  "petty_cash_card": {
    "title": "کارت تنخواه",
    "balance": 7000000.0,
    "total_deposits": 10000000.0,
    "total_withdrawals": 3000000.0,
    "recent_transactions": [
      {
        "id": "7f8c12a8-...",
        "card_type": "PETTY_CASH",
        "card_type_display": "تنخواه",
        "transaction_type": "WITHDRAWAL",
        "transaction_type_display": "برداشت / خرج از کارت",
        "amount": "3000000.00",
        "date": "2026-09-20",
        "date_jalali": "1405/06/30",
        "description": "خرید اقلام بهداشتی و چای",
        "created_by_name": "مدیر مالی",
        "created_at": "2026-09-20T21:00:00Z"
      }
    ]
  },
  "profit_card": {
    "title": "کارت سود",
    "balance": 5000000.0,
    "total_deposits": 5000000.0,
    "total_withdrawals": 0.0,
    "recent_transactions": [
      {
        "id": "6a9b43d1-...",
        "card_type": "PROFIT",
        "card_type_display": "سود",
        "transaction_type": "DEPOSIT",
        "transaction_type_display": "واریز / پرداخت به کارت",
        "amount": "5000000.00",
        "date": "2026-09-20",
        "date_jalali": "1405/06/30",
        "description": "واریز مازاد فروش شنبه به سود",
        "created_by_name": "مدیر مالی",
        "created_at": "2026-09-20T21:15:00Z"
      }
    ]
  }
}
```

> **نکته کلیدی کارت هزینه‌ها:**
> کارت هزینه‌ها به طور زنده مجموع پول‌های ذخیره‌شده (`allocated_amount`) روی هزینه‌های پرداخت‌نشده را نشان می‌دهد. هر زمان هزینه پرداخت قطعی شود (`confirm-payment`)، مبلغ آن از این کارت کسر می‌گردد چون پول برای تسویه نهایی از شرکت خارج شده است.

---

### 2.2. کارت تنخواه - مشاهده تاریخچه و تراکنش‌ها
- **متد:** `GET`
- **آدرس:** `/api/liquidity/cards/petty-cash/`
- **پارامترهای فیلتر (اختیاری):**
  - `?type=DEPOSIT` (فقط واریزها)
  - `?type=WITHDRAWAL` (فقط برداشت‌ها)

### 2.3. کارت تنخواه - ثبت تراکنش واریز یا برداشت
- **متد:** `POST`
- **آدرس:** `/api/liquidity/cards/petty-cash/transactions/`
- **نمونه بدنه درخواست:**
```json
{
  "transaction_type": "DEPOSIT",
  "amount": 5000000,
  "date": "2026-09-21",
  "description": "شارژ تنخواه از فروش نقدی روز قبل"
}
```
*(مقدار `transaction_type` می‌تواند `DEPOSIT` یا `WITHDRAWAL` باشد)*

---

### 2.4. کارت سود - مشاهده تاریخچه و تراکنش‌ها
- **متد:** `GET`
- **آدرس:** `/api/liquidity/cards/profit/`
- **پارامترهای فیلتر (اختیاری):**
  - `?type=DEPOSIT`
  - `?type=WITHDRAWAL`

### 2.5. کارت سود - ثبت تراکنش سود (واریز یا برداشت سود)
- **متد:** `POST`
- **آدرس:** `/api/liquidity/cards/profit/transactions/`
- **نمونه بدنه درخواست:**
```json
{
  "transaction_type": "DEPOSIT",
  "amount": 10000000,
  "date": "2026-09-21",
  "description": "انتقال مازاد فروش به کارت سود"
}
```

### 2.6. حذف یک تراکنش از کارت‌های تنخواه یا سود
- **متد:** `DELETE`
- **آدرس:** `/api/liquidity/cards/transactions/{tx_id}/`

---

## 3️⃣ مدیریت هزینه‌ها (Liquidity Expenses API)

### 3.1. ایجاد هزینه جدید
- **متد:** `POST`
- **آدرس:** `/api/liquidity/expenses/`
- **بدنه درخواست:**
```json
{
  "name": "حقوق مهر پرسنل",
  "category": "SALARY",
  "amount": 200000000,
  "due_date": "2026-10-07",
  "description": "حقوق پرسنل فروش و دفتر مرکزی"
}
```
*(کلید نام می‌تواند `name` یا `title` ارسال شود)*

**دسته‌بندی‌های معتبر (`category`):**
- `SALARY` (حقوق)
- `DAILY` (روزانه)
- `RENT` (اجاره)
- `BILL` (قبض)
- `CHEQUE` (چک)
- `PURCHASE` (خرید)
- `MISC` (متفرقه)

---

### 3.2. دریافت لیست هزینه‌ها و فیلترهای پیشرفته
- **متد:** `GET`
- **آدرس:** `/api/liquidity/expenses/`

#### پارامترهای فیلتر (Query Parameters):
| پارامتر | مقادیر ممکن | توضیحات |
| :--- | :--- | :--- |
| `scope` | `unpaid` **(پیش‌فرض)** | فقط هزینه‌های باز و پرداخت‌نشده |
| | `paid` | فقط هزینه‌های پرداخت‌شده و تسویه شده |
| | `next_week` | هزینه‌های باز با سررسید بین امروز تا ۷ روز آینده |
| | `this_month` | هزینه‌های با سررسید در ماه جاری شمسی |
| | `overdue` | هزینه‌هایی که تاریخ سررسید آن‌ها گذشته و پرداخت نشده‌اند |
| | `all` | تمامی هزینه‌ها بدون تفکیک پرداخت |
| `status` | `CRITICAL` | فقط هزینه‌های خطرناک |
| | `WARNING` | هزینه‌های در وضعیت هشدار |
| | `NORMAL` | هزینه‌های وضعیت عادی |
| | `EXCELLENT` | هزینه‌های عالی (تامین شده قبل از موعد) |
| | `OVERDUE` | هزینه‌های عقب‌مانده |
| | `PAID` | هزینه‌های پرداخت‌شده |
| `category` | `SALARY`, `RENT`, `CHEQUE`, ... | فیلتر بر اساس دسته‌بندی |
| `is_paid` | `true` یا `false` | فیلتر مستقیم وضعیت پرداخت |
| `search` | متن جستجو | جستجو در نام و توضیحات |
| `ordering` | `due_date`, `-due_date`, `amount`, `-amount` | نحوه مرتب‌سازی |

**مثال فراخوانی هزینه‌های هفته آینده:**
```http
GET /api/liquidity/expenses/?scope=next_week
```

**مثال فراخوانی هزینه‌های خطرناک:**
```http
GET /api/liquidity/expenses/?status=CRITICAL
```

---

### 3.3. مشاهده جزئیات یک هزینه
- **متد:** `GET`
- **آدرس:** `/api/liquidity/expenses/{id}/`
- **نمونه پاسخ:**
```json
{
  "id": "e4a30e8c-f831-41b1-b95d-7be38996b940",
  "title": "حقوق مهر پرسنل",
  "name": "حقوق مهر پرسنل",
  "category": "SALARY",
  "category_display": "حقوق",
  "amount": "200000000.00",
  "due_date": "2026-10-07",
  "due_date_jalali": "1405/07/15",
  "description": "حقوق پرسنل فروش و دفتر مرکزی",
  "is_paid": false,
  "paid_at": null,
  "paid_at_jalali": null,
  "allocated_amount": "100000000.00",
  "remaining_debt": "100000000.00",
  "days_remaining": 17,
  "daily_saving_needed": "5882352.94",
  "daily_revenue_ratio": 0.1176,
  "status": "NORMAL",
  "status_display": "عادی",
  "payments": [
    {
      "id": "2d1b82ff-...",
      "expense": "e4a30e8c-...",
      "amount": "50000000.00",
      "date": "2026-09-20",
      "date_jalali": "1405/06/30",
      "description": "تخصیص اول از فروش شنبه",
      "created_by": 1,
      "created_by_name": "مدیر مالی",
      "created_at": "2026-09-20T21:40:00Z"
    },
    {
      "id": "5c4d91aa-...",
      "expense": "e4a30e8c-...",
      "amount": "50000000.00",
      "date": "2026-09-21",
      "date_jalali": "1405/06/31",
      "description": "تخصیص دوم از فروش یکشنبه",
      "created_by": 1,
      "created_by_name": "مدیر مالی",
      "created_at": "2026-09-21T08:30:00Z"
    }
  ],
  "created_by": 1,
  "created_by_name": "مدیر مالی",
  "created_at": "2026-09-20T21:30:00Z",
  "updated_at": "2026-09-20T21:40:00Z"
}
```

---

### 3.4. ویرایش و حذف هزینه
- **ویرایش مشخصات:** `PUT` یا `PATCH` به `/api/liquidity/expenses/{id}/`
- **حذف هزینه:** `DELETE` به `/api/liquidity/expenses/{id}/`

---

## 4️⃣ پرداخت‌های مرحله‌ای و تخصیص وجوه به هزینه (Payments API)

### 4.1. ثبت پرداخت / واریز ذخیره‌سازی به یک هزینه
- **متد:** `POST`
- **آدرس:** `/api/liquidity/expenses/{id}/payments/`
- **نمونه بدنه درخواست:**
```json
{
  "amount": 25000000,
  "date": "2026-09-21",
  "description": "تخصیص از نقدینگی فروش روز گذشته"
}
```
*(فیلد `date` اختیاری است و در صورت عدم ارسال، تاریخ روز جاری لحاظ می‌شود)*

- **پاسخ:** وضعیت `201 Created` شامل رکورد پرداخت ثبت‌شده و اطلاعات به‌روزشده هزینه (با `allocated_amount` و `status` جدید).

### 4.2. حذف یا لغو یک پرداخت مرحله‌ای
- **متد:** `DELETE`
- **آدرس:** `/api/liquidity/expenses/{id}/payments/{payment_id}/`
- **پاسخ:** وضعیت `200 OK` به همراه بازگردانی محاسبات هزینه.

---

## 5️⃣ تسویه نهایی و تایید پرداخت هزینه (Settlement API)

### 5.1. تایید نهایی پرداخت هزینه (Confirm Payment)
وقتی تاریخ پرداخت فرا برسد و مدیر مالی وجه را به طور کامل تسویه کند، با فراخوانی این اندپوینت هزینه تایید می‌شود:
- **متد:** `POST`
- **آدرس:** `/api/liquidity/expenses/{id}/confirm-payment/`
- **نتیجه:**
  - وضعیت هزینه به `PAID` تبدیل می‌شود.
  - این هزینه از دایره هزینه‌های جاری خارج می‌شود.
  - **مبلغ آن به طور خودکار از کارت هزینه‌ها کسر می‌گردد.**
  - فیلدهای `is_paid: true` و `paid_at` مقداردهی می‌شوند.

### 5.2. بازگردانی وضعیت به پرداخت‌نشده (Unconfirm Payment)
در صورتی که تایید پرداخت اشتباهاً ثبت شده باشد:
- **متد:** `POST`
- **آدرس:** `/api/liquidity/expenses/{id}/unconfirm-payment/`

---

## 6️⃣ خلاصه شمارنده‌ها و نشان‌ها (Summary / Badges API)

مناسب برای ساخت تب‌ها، منو و بج‌های بالای صفحات فرانت‌اند بدون نیاز به لود کل لیست:
- **متد:** `GET`
- **آدرس:** `/api/liquidity/expenses/summary/`
- **نمونه پاسخ:**
```json
{
  "total_count": 15,
  "unpaid_count": 8,
  "paid_count": 7,
  "next_week_count": 3,
  "overdue_count": 1,
  "critical_count": 1,
  "warning_count": 2,
  "normal_count": 4,
  "excellent_count": 1,
  "total_unpaid_amount": 420000000.0,
  "total_allocated_amount": 165000000.0,
  "total_remaining_amount": 255000000.0
}
```
