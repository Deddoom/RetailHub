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

## 2️⃣ کارت‌های ۹‌گانه نقدینگی (Cards API)

سامانه نقدینگی دارای ۹ کارت اختصاصی متناظر با دسته‌بندی‌های هزینه‌ها است:
1. **تامین کننده** (`SUPPLIER`)
2. **حقوق** (`SALARY`)
3. **اجاره** (`RENT`)
4. **اقساط** (`INSTALLMENTS`)
5. **سایر هزینه ها** (`OTHER_EXPENSES`)
6. **مدیریت** (`MANAGEMENT`)
7. **پس انداز** (`SAVINGS`)
8. **خیریه** (`CHARITY`)
9. **تجهیزات** (`EQUIPMENT`)

هر کارت شامل اطلاعات زیر است:
- **`balance`:** مانده و اعتبار فعلی کارت (مجموع واریزی‌ها منهای مجموع برداشت‌ها).
- **`total_expenses`:** مجموع مبالغ هزینه‌های **پرداخت‌نشده** مربوط به این دسته که تاریخ سررسید آن‌ها تا **۳۰ روز آینده** است (شامل هزینه‌های معوقه تسویه‌نشده). هزینه‌های با سررسید بیش از ۳۰ روز محاسبه نمی‌شوند تا وارد بازه ۳۰ روزه شوند.
- **`expenses_count`:** تعداد هزینه‌های باز این دسته تا ۳۰ روز آینده.
- **`total_deposits` و `total_withdrawals`:** مجموع مبالغ شارژ و خروجی.
- **`recent_transactions`:** لیست آخرین تراکنش‌های انجام‌شده در این کارت.

---

### 2.1. مشاهده نمای کلی وضعیت هر ۹ کارت (Overview)
- **متد:** `GET`
- **آدرس:** `/api/liquidity/cards/` (یا `/api/liquidity/cards/overview/`)
- **نمونه پاسخ:**
```json
{
  "summary": {
    "total_balance": 250000000.0,
    "total_expenses": 140000000.0,
    "total_deposits": 300000000.0,
    "total_withdrawals": 50000000.0
  },
  "cards": [
    {
      "card_type": "RENT",
      "title": "کارت اجاره",
      "balance": 200000000.0,
      "total_deposits": 200000000.0,
      "total_withdrawals": 0.0,
      "total_expenses": 60000000.0,
      "expenses_count": 3,
      "recent_transactions": [...]
    },
    {
      "card_type": "SALARY",
      "title": "کارت حقوق",
      "balance": 50000000.0,
      "total_deposits": 100000000.0,
      "total_withdrawals": 50000000.0,
      "total_expenses": 80000000.0,
      "expenses_count": 2,
      "recent_transactions": [...]
    }
  ],
  "cards_by_type": {
    "supplier": { ... },
    "salary": { ... },
    "rent": { ... },
    "installments": { ... },
    "other_expenses": { ... },
    "management": { ... },
    "savings": { ... },
    "charity": { ... },
    "equipment": { ... }
  }
}
```

---

### 2.2. مشاهده جزئیات و تاریخچه تراکنش‌های یک کارت
- **متد:** `GET`
- **آدرس:** `/api/liquidity/cards/{card_type}/`
  *(مثال‌ها: `/api/liquidity/cards/rent/`، `/api/liquidity/cards/salary/`، `/api/liquidity/cards/other-expenses/`)*
- **پارامترهای فیلتر (اختیاری):**
  - `?type=DEPOSIT` (فقط واریزها)
  - `?type=WITHDRAWAL` (فقط برداشت‌ها)

---

### 2.3. ثبت تراکنش واریز یا برداشت کارت
- **متد:** `POST`
- **آدرس:** `/api/liquidity/cards/{card_type}/transactions/` یا `/api/liquidity/cards/transactions/`
- **نمونه بدنه درخواست:**
```json
{
  "transaction_type": "DEPOSIT",
  "amount": 50000000,
  "date": "2026-10-06",
  "description": "شارژ کارت اجاره از محل فروش نقدی"
}
```
*(مقدار `transaction_type` می‌تواند `DEPOSIT` (واریز) یا `WITHDRAWAL` (برداشت) باشد. در صورت ارسال به اندپوینت عمومی، فیلد `"card_type": "RENT"` در بدنه الزامی است).*

---

### 2.4. حذف یک تراکنش از کارت
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
  "due_date": "2026-10-25",
  "description": "حقوق پرسنل فروش و دفتر مرکزی"
}
```
*(کلید نام می‌تواند `name` یا `title` ارسال شود)*

**دسته‌بندی‌های معتبر (`category`):**
- `SUPPLIER` (تامین کننده)
- `SALARY` (حقوق)
- `RENT` (اجاره)
- `INSTALLMENTS` (اقساط)
- `OTHER_EXPENSES` (سایر هزینه ها)
- `MANAGEMENT` (مدیریت)
- `SAVINGS` (پس انداز)
- `CHARITY` (خیریه)
- `EQUIPMENT` (تجهیزات)

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
وقتی تاریخ پرداخت فرا برسد و مدیر مالی وجه را تسویه کند، با فراخوانی این اندپوینت تایید نهایی ثبت می‌شود:
- **متد:** `POST`
- **آدرس:** `/api/liquidity/expenses/{id}/confirm-payment/`
- **منطق و کنترل اعتبارسنجی سخت‌گیرانه (Strict Balance Check):**
  1. سیستم ابتدا موجودی کارت متناظر با دسته‌بندی این هزینه (مثلاً کارت اجاره) را بررسی می‌کند.
  2. **در صورت کسری موجودی کارت:** خطای `400 Bad Request` برمی‌گرداند و مانع پرداخت می‌شود:
     ```json
     {
       "error": "موجودی کارت اجاره (20,000,000 تومان) برای پرداخت این هزینه (50,000,000 تومان) کافی نیست. ابتدا کارت را شارژ کنید."
     }
     ```
  3. **در صورت کافی بودن موجودی کارت:**
     - وضعیت هزینه به `is_paid: true` و `PAID` تبدیل می‌شود.
     - به طور خودکار یک تراکنش **برداشت (`WITHDRAWAL`)** به مبلغ هزینه از کارت همان دسته کسر و ثبت می‌گردد (مثلاً مانده ۲۰۰ میلیون به ۱۵۰ میلیون تومان کاهش می‌یابد).
     - این هزینه از فیلد **«مجموع هزینه» (`total_expenses`)** آن کارت خارج می‌شود.

### 5.2. بازگردانی وضعیت به پرداخت‌نشده (Unconfirm Payment)
در صورتی که تایید پرداخت اشتباهاً ثبت شده باشد:
- **متد:** `POST`
- **آدرس:** `/api/liquidity/expenses/{id}/unconfirm-payment/`
- **نتیجه:**
  - وضعیت هزینه به `is_paid: false` بازمی‌گردد.
  - تراکنش برداشت خودکار حذف/باطل می‌شود.
  - مبلغ به موجودی کارت بازگردانده شده و هزینه مجدداً در «مجموع هزینه» کارت محاسبه می‌گردد.

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
