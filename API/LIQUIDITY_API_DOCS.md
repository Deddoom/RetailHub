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

وضعیت هر هزینه به صورت لحظه‌ای بر اساس **شاخص فشار نقدینگی (کسر نقدینگی)**، موجودی کارت دسته‌بندی مربوطه، ورودی سهم دسته‌بندی از فروش روزانه و کسر هزینه‌های بالادستی همان دسته محاسبه می‌شود:

### ۱. درصدهای مصوب سهم دسته‌بندی‌ها از فروش روزانه ($P_C$):
| دسته‌بندی | کد انگلیسی | سهم از فروش روزانه |
| :--- | :--- | :--- |
| **تامین کننده** | `SUPPLIER` | **۵۱٪** |
| **حقوق** | `SALARY` | **۱۴٪** |
| **اجاره** | `RENT` | **۵٪** |
| **اقساط** | `INSTALLMENTS` | **۹٪** |
| **سایر هزینه ها** | `OTHER_EXPENSES` | **۷٪** |
| **مدیریت** | `MANAGEMENT` | **۳٪** |
| **پس انداز** | `SAVINGS` | **۷٪** |
| **خیریه** | `CHARITY` | **۲٪** |
| **تجهیزات** | `EQUIPMENT` | **۲٪** |

### ۲. فرمول محاسبه نقدینگی در دسترس و کسر فشار هزینه:
- **ورودی پیش‌بینی‌شده نقدی تا سررسید:**
  $$\text{ExpectedIncoming} = \text{DailyRevenue} \times P_C \times \max(0, \text{DaysRemaining})$$
- **نقدینگی خالص در دسترس در تاریخ سررسید (مخرج کسر):**
  $$\text{AvailableCash} = \text{CardBalance}_C + \text{ExpectedIncoming} - \text{UpstreamExpenses}_C$$
  *(هزینه‌های بالادستی / $\text{UpstreamExpenses}_C$: مجموع مبالغ هزینه‌های پرداخت‌نشده در همین دسته‌بندی که تاریخ سررسید آن‌ها زودتر از این هزینه است).*
- **کسر شاخص فشار نقدینگی (صورت بر مخرج):**
  $$\text{Ratio} = \frac{\text{Amount}}{\text{AvailableCash}}$$

### ۳. کدهای وضعیت و آستانه‌های وقوع:
| کد وضعیت | عنوان فارسی | شرط وقوع | تحلیل کسب‌وکاری |
| :--- | :--- | :--- | :--- |
| `PAID` | پرداخت شده | `is_paid = true` | هزینه تسویه نهایی شده است. |
| `OVERDUE` | عقب مانده | `days_remaining < 0` و پرداخت نشده | تاریخ سررسید سپری شده است. |
| `CRITICAL` | خطرناک | $\text{Ratio} \ge 1.0$ یا $\text{AvailableCash} \le 0$ | نقدینگی در دسترس حتی برای تسویه این هزینه کافی نیست. |
| `WARNING` | هشدار | $0.80 \le \text{Ratio} < 1.0$ | هزینه بین ۸۰٪ تا ۱۰۰٪ نقدینگی در دسترس را مصرف می‌کند (ریسک کسری با افت فروش). |
| `NORMAL` | عادی | $0.30 \le \text{Ratio} < 0.80$ | هزینه بین ۳۰٪ تا ۸۰٪ نقدینگی پیش‌بینی‌شده است (وضعیت متعادل و باثبات). |
| `EXCELLENT` | عالی | $\text{Ratio} < 0.30$ | هزینه کمتر از ۳۰٪ نقدینگی پیش‌بینی‌شده را شامل می‌شود (پوشش بسیار بالا و ایمن). |

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

### 2.4. دریافت لیست تجمیعی کلیه تراکنش‌های مالی کارت‌ها (واریز، برداشت و پرداخت هزینه)
- **متد:** `GET`
- **آدرس:** `/api/liquidity/cards/transactions/` (یا `/api/liquidity/cards/all-transactions/`)
- **دسترسی:** کاربران مدیر نقدینگی (`ADMIN`، `FINANCIAL_MANAGER`)
- **مرتب‌سازی:** به ترتیب نزولی تاریخ و زمان وقوع (`-date, -created_at`)
- **صفحه‌بندی الزامی (Pagination):** خروجی به صورت پیش‌فرض با اندازه صفحه ۲۰تایی ارائه می‌شود.

#### پارامترهای فیلتر (Query Parameters):
| پارامتر | نوع | توضیح |
|---|---|---|
| `page` | عدد صحیح | شماره صفحه (پیش‌فرض: `1`) |
| `page_size` | عدد صحیح | تعداد آیتم در صفحه (پیش‌فرض: `20`، حداکثر: `100`) |
| `card_type` | رشته | فیلتر روی یک کارت معین (مانند: `salary`, `rent`, `supplier`, `installments`, `other_expenses`, ...) |
| `type` | رشته | فیلتر نوع تراکنش: `deposit` (واریزی‌ها), `withdrawal` (برداشت‌های عادی), `expense` (پرداخت و کسر هزینه‌ها) |
| `from_date` | تاریخ (`YYYY-MM-DD`) | از تاریخ |
| `to_date` | تاریخ (`YYYY-MM-DD`) | تا تاریخ |
| `search` | متن | جستجو در توضیحات تراکنش یا عنوان هزینه تسویه‌شده |

#### نمونه پاسخ (HTTP 200 OK):
```json
{
  "count": 142,
  "total_pages": 8,
  "current_page": 1,
  "page_size": 20,
  "next": "http://.../api/liquidity/cards/transactions/?page=2",
  "previous": null,
  "results": [
    {
      "id": "e98e29a1-0a12-48e1-83fb-b4cba8c162d1",
      "date": "2026-10-22",
      "date_jalali": "1405/07/30",
      "amount": "15000000.00",
      "transaction_type": "WITHDRAWAL",
      "transaction_type_code": "EXPENSE_PAYMENT",
      "transaction_type_display": "پرداخت هزینه",
      "card_type": "RENT",
      "card_title": "کارت اجاره",
      "expense_id": "84b3d81b-56e9-40b5-a63c-da1eb87d6c9a",
      "expense_title": "اجاره ماه مهر شعبه بهشتی",
      "expense_category": "RENT",
      "expense_category_display": "اجاره",
      "description": "تسویه و پرداخت هزینه: اجاره ماه مهر شعبه بهشتی",
      "created_by": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "created_by_name": "امیر حسینی",
      "created_at": "2026-10-22T10:15:30Z"
    },
    {
      "id": "18cf793a-fe97-49ea-aee3-1e9bf59590fc",
      "date": "2026-10-21",
      "date_jalali": "1405/07/29",
      "amount": "50000000.00",
      "transaction_type": "DEPOSIT",
      "transaction_type_code": "DEPOSIT",
      "transaction_type_display": "واریز به کارت",
      "card_type": "SALARY",
      "card_title": "کارت حقوق",
      "expense_id": null,
      "expense_title": null,
      "expense_category": null,
      "expense_category_display": null,
      "description": "شارژ کارت حقوق از محل فروش روزانه",
      "created_by": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "created_by_name": "امیر حسینی",
      "created_at": "2026-10-21T18:00:00Z"
    }
  ]
}
```

---

### 2.5. حذف یک تراکنش از کارت
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
  "daily_revenue_ratio": 0.45,
  "ratio": 0.45,
  "category_percentage": 0.14,
  "card_balance": "50000000.00",
  "upstream_expenses": "30000000.00",
  "expected_incoming": "119000000.00",
  "available_cash": "139000000.00",
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

---

## 7️⃣ شارژ روزانه نقدینگی با تفکیک شعب و مطالبات (Detailed Daily Charges API)

امکان ثبت دقیق ورودی‌های نقدی روزانه با تفکیک ۴ شعبه (بهشتی، سپیده، مدرس، کاجستان) در ۳ روش پرداخت، به همراه وصول مطالبات و چک‌های پاس‌شده.

### 7.1. ثبت شارژ روزانه جدید (Create)
- **متد:** `POST`
- **آدرس:** `/api/liquidity/daily-charges/`
- **نمونه بدنه درخواست (JSON):**
```json
{
  "date": "2026-10-10",
  "beheshti_pos": 10000000,
  "beheshti_cash": 2000000,
  "beheshti_card_to_card": 3000000,
  "sepideh_pos": 5000000,
  "sepideh_cash": 1000000,
  "sepideh_card_to_card": 2000000,
  "modarres_pos": 7000000,
  "modarres_cash": 3000000,
  "modarres_card_to_card": 0,
  "kajestan_pos": 4000000,
  "kajestan_cash": 1000000,
  "kajestan_card_to_card": 1000000,
  "debt_collection": 5000000,
  "passed_checks_amount": 8000000,
  "description": "شارژ تفکیکی روز شنبه"
}
```
*(تمامی فیلدها اختیاری بوده و مقدار پیش‌فرض آنها صفر است. فیلد `date` در صورت ارسال نشدن، تاریخ روز جاری لحاظ می‌گردد)*

- **پاسخ (`201 Created`):**
```json
{
  "id": "76ef231d-...",
  "date": "2026-10-10",
  "date_jalali": "1405/07/19",
  "amount": "52000000.00",
  "total_sales": "52000000.00",
  "description": "شارژ تفکیکی روز شنبه",
  "beheshti_pos": "10000000.00",
  "beheshti_cash": "2000000.00",
  "beheshti_card_to_card": "3000000.00",
  "beheshti_total": "15000000.00",
  "sepideh_pos": "5000000.00",
  "sepideh_cash": "1000000.00",
  "sepideh_card_to_card": "2000000.00",
  "sepideh_total": "8000000.00",
  "modarres_pos": "7000000.00",
  "modarres_cash": "3000000.00",
  "modarres_card_to_card": "0.00",
  "modarres_total": "10000000.00",
  "kajestan_pos": "4000000.00",
  "kajestan_cash": "1000000.00",
  "kajestan_card_to_card": "1000000.00",
  "kajestan_total": "6000000.00",
  "branch_sales_total": "39000000.00",
  "debt_collection": "5000000.00",
  "passed_checks_amount": "8000000.00",
  "created_by": 1,
  "created_by_name": "مدیر مالی",
  "created_at": "2026-10-12T05:30:00Z",
  "shamsi_date": "1405/07/21",
  "shamsi_time": "09:00"
}
```

### 7.2. لیست شارژهای روزانه (List & Filter)
- **متد:** `GET`
- **آدرس:** `/api/liquidity/daily-charges/`
- **پارامترهای فیلتر اختیاری:**
  - `from_date=2026-10-01`: فیلتر از تاریخ
  - `to_date=2026-10-30`: فیلتر تا تاریخ

---

## 8️⃣ مدیریت چک‌های دریافتی (Checks Management API)

### 8.1. گزینه‌های وضعیت و شعب
- **کدهای وضعیت (`status`):**
  - `CLEARED`: وصول شده (تسویه شده)
  - `PENDING`: نرسیده (موعد سررسید فرا نرسیده)
  - `UNPAID`: عدم پرداخت (تاریخ سررسید رد شده و وجه پاس نشده)
  - `BOUNCED`: برگشتی
  - `SPENT`: خرج شده (به یک هزینه تخصیص داده شده)
- **کدهای شعب (`branch`):**
  - `BEHESHTI`: شعبه بهشتی
  - `MODARRES`: شعبه مدرس
  - `SEPIDEH`: شعبه سپیده
  - `KAJESTAN`: شعبه کاجستان
  - `ALL`: کل مجموعه

> [!NOTE]
> **انتقال خودکار وضعیت چک:** در هر بار فراخوانی لیست چک‌ها یا جزئیات، اگر موعد سررسید چکی گذشته باشد و وضعیت آن هنوز «نرسیده» (`PENDING`) باشد، سیستم به صورت کاملاً خودکار وضعیت آن را به «عدم پرداخت» (`UNPAID`) تبدیل می‌کند.

### 8.2. ثبت چک جدید
- **متد:** `POST`
- **آدرس:** `/api/liquidity/checks/`
- **بدنه درخواست:**
```json
{
  "customer_name": "بازرگانی محمدی",
  "issue_date": "2026-10-10",
  "due_date": "2026-11-15",
  "amount": 25000000,
  "branch": "BEHESHTI",
  "status": "PENDING",
  "description": "چک صیادی بابت فاکتور شماره ۱۲۴"
}
```

### 8.3. دریافت لیست چک‌ها (با فیلترهای پیشرفته)
- **متد:** `GET`
- **آدرس:** `/api/liquidity/checks/`
- **پارامترهای فیلتر:**
  - `status=PENDING`
  - `branch=BEHESHTI`
  - `from_date=2026-10-01`
  - `to_date=2026-11-30`
  - `search=محمدی` (جستجو در نام مشتری و توضیحات)
  - `available_for_expense=true` (فقط چک‌های نرسیده یا عدم پرداخت که خرج نشده‌اند؛ مناسب باز کردن دراپ‌داون انتخاب چک برای خرج روی هزینه)

### 8.4. آمار و خلاصه وضعیت چک‌ها (Summary Badges)
- **متد:** `GET`
- **آدرس:** `/api/liquidity/checks/summary/`
- **نمونه پاسخ:**
```json
{
  "total_count": 12,
  "total_amount": 350000000.0,
  "cleared_count": 4,
  "cleared_amount": 100000000.0,
  "pending_count": 5,
  "pending_amount": 150000000.0,
  "unpaid_count": 1,
  "unpaid_amount": 25000000.0,
  "bounced_count": 1,
  "bounced_amount": 25000000.0,
  "spent_count": 1,
  "spent_amount": 50000000.0
}
```

### 8.5. ویرایش یا تغییر وضعیت چک
- **متد:** `PATCH` یا `PUT`
- **آدرس:** `/api/liquidity/checks/{id}/`
- **نمونه تغییر وضعیت به وصول‌شده:**
```json
{
  "status": "CLEARED"
}
```

---

## 9️⃣ خرج چک روی هزینه‌ها (Spending Checks on Expenses API)

وقتی چکی پشت‌نویسی شده و به یک تامین‌کننده یا بابت هزینه‌ای خرج می‌شود:

### 9.1. اختصاص چک(ها) به یک هزینه (Spend Checks)
- **متد:** `POST`
- **آدرس:** `/api/liquidity/expenses/{id}/spend-checks/`
- **بدنه درخواست:**
```json
{
  "check_ids": [
    "c58a2d10-38e5-4f4a-89a1-...",
    "e91a27b8-6411-482a-bc3e-..."
  ]
}
```
- **رفتار و اثرات در سیستم:**
  1. وضعیت چک‌ها به `SPENT` تبدیل می‌شود و به این هزینه لینک می‌شوند.
  2. فیلد `has_spent_check: true` برای هزینه فعال می‌شود.
  3. فیلد `initial_amount` هزینه مبلغ کل اولیه را نگه می‌دارد (مثلاً ۲۰۰ میلیون).
  4. فیلد `spent_checks_amount` مجموع چک‌های اختصاص یافته است (مثلاً ۲۰ میلیون).
  5. مبلغ `amount` هزینه به ۱۸۰ میلیون کاهش می‌یابد تا هنگام تسویه نقدی (`confirm-payment`)، سیستم فقط ۱۸۰ میلیون را از موجودی کارت کسر کند.

### 9.2. لغو و جداسازی چک خرج‌شده از هزینه (Remove Spent Check)
در صورتی که چک اشتباهاً اختصاص یافته باشد یا لغو شود:
- **متد:** `POST`
- **آدرس:** `/api/liquidity/expenses/{id}/remove-spent-check/`
- **بدنه درخواست:**
```json
{
  "check_id": "c58a2d10-38e5-4f4a-89a1-..."
}
```
- **نتیجه:** وضعیت چک به `PENDING` (یا `UNPAID` در صورت گذشتن سررسید) بازگشته و مبلغ خالص هزینه به میزان مبلغ چک افزایش می‌یابد.

