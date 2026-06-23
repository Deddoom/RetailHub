# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import AbstractUser
from uuid import uuid4
from decimal import Decimal


# ── تعریف شعب ثابت سیستم ──────────────────────────────────────────────────
BRANCH_CHOICES = [
    ('شعبه بهشتی',  'شعبه بهشتی'),
    ('شعبه مدرس',   'شعبه مدرس'),
    ('شعبه سپیده',  'شعبه سپیده'),
    ('شعبه کاجستان','شعبه کاجستان'),
]

# ── درخت سلسله‌مراتب نقش‌ها ────────────────────────────────────────────────
# کلید: نقش بالادست  →  مقدار: مجموعه نقش‌هایی که مستقیماً زیرمجموعه آن هستند
# برای پیمایش چندسطحی از تابع کمکی _get_all_subordinate_codes استفاده می‌شود
ROLE_TREE: dict[str, set[str]] = {
    'ADMIN':             {'FINANCIAL_MANAGER', 'EXECUTIVE_MANAGER', 'SUPERVISOR',
                          'ACCOUNTANT', 'STATISTICIAN', 'CASHIER', 'USER'},
    'FINANCIAL_MANAGER': {'ACCOUNTANT', 'STATISTICIAN', 'CASHIER', 'USER'},
    'EXECUTIVE_MANAGER': {'SUPERVISOR', 'USER'},
    'SUPERVISOR':        {'USER'},
    'ACCOUNTANT':        {'CASHIER', 'USER'},
    'STATISTICIAN':      set(),
    'CASHIER':           set(),
    'USER':              set(),
}


def _get_all_subordinate_codes(role_codes: list[str]) -> set[str]:
    """
    با توجه به لیست نقش‌های یک کاربر، تمام نقش‌هایی را که او بر آن‌ها
    بالادستی دارد (به‌صورت تجمیعی در کل درخت) برمی‌گرداند.
    """
    result: set[str] = set()
    queue  = list(role_codes)
    while queue:
        current = queue.pop()
        children = ROLE_TREE.get(current, set())
        new = children - result
        result |= new
        queue.extend(new)
    return result


class Role(models.Model):
    ROLE_CHOICES = [
        ('ADMIN',             'مدیریت (Admin)'),
        ('FINANCIAL_MANAGER', 'مدیر مالی'),
        ('EXECUTIVE_MANAGER', 'مدیر اجرایی'),
        ('SUPERVISOR',        'سرپرست'),
        ('ACCOUNTANT',        'حسابدار'),
        ('STATISTICIAN',      'آمارگیر'),
        ('CASHIER',           'صندوق‌دار'),
        ('USER',              'کارکنان عادی'),
    ]
    id   = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    code = models.CharField(max_length=30, choices=ROLE_CHOICES, unique=True)

    def __str__(self):
        return self.get_code_display()


class CustomUser(AbstractUser, SafeDestroyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.CharField(max_length=50, choices=BRANCH_CHOICES, null=True, blank=True)
    roles = models.ManyToManyField('Role', blank=True, related_name='users')
    
    # فیلد جدید برای بررسی اینکه کاربر نام و فامیل خود را در اولین ورود ثبت کرده است یا خیر
    is_profile_completed = models.BooleanField(default=False)

    def __str__(self):
        # اگر نام یا نام‌خانوادگی ثبت شده باشد، آن را در کنار یوزرنیم نشان می‌دهد تا ادمین راحت‌تر تشخیص دهد
        if self.first_name or self.last_name:
            return f"{self.username} ({self.first_name} {self.last_name})".strip()
        return self.username

    def is_superior_to(self, other_user):
        """
        منطق بررسی بالادست بودن کاربر (کدهای قبلی شما)
        """
        if self.is_superuser:
            return True
        if other_user.is_superuser:
            return False

        # ادمین به همه دسترسی دارد
        if self.roles.filter(code='ADMIN').exists():
            return True
        if other_user.roles.filter(code='ADMIN').exists():
            return False

        # سوپروایزر به حسابدار و کارکنان عادی دسترسی دارد
        if self.roles.filter(code='SUPERVISOR').exists():
            return other_user.roles.filter(code__in=['ACCOUNTANT', 'USER']).exists()

        # حسابدار فقط به کارکنان عادی دسترسی دارد
        if self.roles.filter(code='ACCOUNTANT').exists():
            return other_user.roles.filter(code='USER').exists()

        return False


# ── Mission ────────────────────────────────────────────────────────────────────
class Mission(models.Model):
    STATUS_CHOICES = [
        ('PENDING',   'در انتظار انجام'),
        ('DOING',     'در حال انجام'),
        ('COMPLETED', 'انجام شده'),
        ('CANCELLED', 'لغو شده'),
    ]
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title       = models.CharField(max_length=150)
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='missions')
    created_by  = models.ForeignKey(CustomUser, on_delete=models.PROTECT,  related_name='created_missions')
    start_date  = models.DateTimeField()
    end_date    = models.DateTimeField()
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ماموریت: {self.title} برای {self.assigned_to.username}"


# ── Seller ─────────────────────────────────────────────────────────────────────
class Seller(models.Model):
    id     = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name   = models.CharField(max_length=150)
    phone  = models.CharField(max_length=15, unique=True, blank=True, null=True)
    branch = models.CharField(max_length=50, choices=BRANCH_CHOICES)

    def __str__(self):
        return f"{self.name} - {self.branch}"


# ── Customer ───────────────────────────────────────────────────────────────────
class Customer(models.Model):
    PRIMARY_GOODS_CHOICES = [
        ('APARTMENT',  'آپارتمانی'),
        ('OUTDOOR',    'بیرونی'),
        ('FERTILIZER', 'کود'),
        ('NEHAL',      'نهال'),
        ('POT',        'گلدان'),
        ('OTHER',      'متفرقه'),
    ]
    BUYING_FOR_CHOICES = [
        ('GARDEN', 'باغ'),
        ('HOUSE',  'خانه'),
        ('SHOP',   'مغازه'),
        ('OTHER',  'متفرقه'),
    ]
    id                    = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name                  = models.CharField(max_length=150)
    phone                 = models.CharField(max_length=15, unique=True)
    address               = models.TextField(blank=True, null=True)
    primary_goods         = models.CharField(max_length=50, choices=PRIMARY_GOODS_CHOICES, default='OTHER')
    buying_for            = models.CharField(max_length=50, choices=BUYING_FOR_CHOICES,    default='OTHER')
    last_purchase_date    = models.DateField(blank=True, null=True)
    total_purchase_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    last_purchase_type    = models.CharField(max_length=30, blank=True, null=True)
    description           = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"


# ── Sale ───────────────────────────────────────────────────────────────────────
class Sale(models.Model):
    id                = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    total_amount      = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date_time         = models.DateTimeField(auto_now_add=True)
    branch            = models.CharField(max_length=50, choices=BRANCH_CHOICES)
    seller            = models.ForeignKey(Seller,     on_delete=models.PROTECT, related_name='sales')
    customer          = models.ForeignKey(Customer,   on_delete=models.PROTECT, related_name='sales', blank=True, null=True)
    created_by        = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='sales_created')
    description       = models.TextField(blank=True, null=True)


# ── Payment ────────────────────────────────────────────────────────────────────
class Payment(models.Model):
    METHOD_CHOICES = [
        ('CASH',        'نقدی'),
        ('CARD_TO_CARD','کارت به کارت'),
        ('SHEBA',       'شبا'),
        ('POS',         'کارتخوان'),
        ('COMBINED',    'ترکیبی'),
        ('REMAINING',   'وجه مانده'),
        ('DEPOSIT',     'بیعانه'),
        ('CHEQUE',      'چک صیادی/عادی'),
    ]
    id             = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    sale           = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    description    = models.TextField(blank=True, null=True)


# ── Expense ────────────────────────────────────────────────────────────────────
class Expense(models.Model):
    METHOD_CHOICES = [
        ('CASH',               'نقدی'),
        ('CARD',               'کارتی'),
        ('ACCOUNT_TO_ACCOUNT', 'حساب به حساب'),
        ('COMBINED',           'ترکیبی'),
        ('CHEQUE',             'چکی'),
    ]
    id                = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    amount            = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method    = models.CharField(max_length=30, choices=METHOD_CHOICES)
    date              = models.DateField()
    category          = models.CharField(max_length=100)
    branch            = models.CharField(max_length=50, choices=BRANCH_CHOICES)
    invoice_image_url = models.URLField(max_length=500, blank=True, null=True)
    created_by        = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='expenses_created')
    description       = models.TextField(blank=True, null=True)


# ── Cheque ─────────────────────────────────────────────────────────────────────
class Cheque(models.Model):
    id               = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    payment          = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='cheques', blank=True, null=True)
    expense          = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='cheques', blank=True, null=True)
    due_date         = models.DateField()
    cheque_number    = models.CharField(max_length=50, unique=True)
    amount           = models.DecimalField(max_digits=12, decimal_places=2)
    customer_phone   = models.CharField(max_length=15,  blank=True, null=True)
    customer_name    = models.CharField(max_length=150, blank=True, null=True)
    is_endorsed      = models.BooleanField(default=False)
    cheque_image_url = models.URLField(max_length=500, blank=True, null=True)
    description      = models.TextField(blank=True, null=True)


# ── DepositItem ────────────────────────────────────────────────────────────────
class DepositItem(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    sale        = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='deposit_items')
    item_name   = models.CharField(max_length=150)
    quantity    = models.IntegerField()
    unit_price  = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)


# ── DamageReport ───────────────────────────────────────────────────────────────
class DamageReport(models.Model):
    id             = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    item_name      = models.CharField(max_length=150)
    quantity       = models.IntegerField()
    estimated_loss = models.DecimalField(max_digits=12, decimal_places=2)
    date           = models.DateField()
    branch         = models.CharField(max_length=50, choices=BRANCH_CHOICES)
    description    = models.TextField(blank=True, null=True)
    created_by     = models.ForeignKey(CustomUser, on_delete=models.PROTECT)


# ── ItemExit ───────────────────────────────────────────────────────────────────
class ItemExit(models.Model):
    REASON_CHOICES = [
        ('RETURN',   'مرجوعی به تامین‌کننده'),
        ('DAMAGE',   'خرابی و ضایعات'),
        ('INTERNAL', 'مصرف داخلی'),
    ]
    id         = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    item_name  = models.CharField(max_length=150)
    quantity   = models.IntegerField()
    reason     = models.CharField(max_length=50, choices=REASON_CHOICES)
    date       = models.DateField()
    branch     = models.CharField(max_length=50, choices=BRANCH_CHOICES)
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT)


# ── Checklist ──────────────────────────────────────────────────────────────────
class Checklist(models.Model):
    FREQUENCY_CHOICES = [
        ('DAILY',   'روزانه'),
        ('WEEKLY',  'هفتگی'),
        ('MONTHLY', 'ماهانه'),
    ]
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title       = models.CharField(max_length=150)
    frequency   = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='DAILY')
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assigned_checklists', null=True, blank=True)
    created_by  = models.ForeignKey(CustomUser, on_delete=models.PROTECT,  related_name='created_checklists')
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"چک‌لیست {self.get_frequency_display()} - {self.title}"


# ── Task ───────────────────────────────────────────────────────────────────────
class Task(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    checklist    = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='tasks')
    title        = models.CharField(max_length=150)
    is_completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    description  = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title


# ── DepositOrder ───────────────────────────────────────────────────────────────
class DepositOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING',   'در انتظار تحویل'),
        ('DELIVERED', 'تحویل داده شده'),
        ('CANCELLED', 'لغو شده'),
    ]
    DEPOSIT_PAYMENT_CHOICES = [
        ('CASH',        'نقدی'),
        ('CARD_TO_CARD','کارت به کارت'),
        ('CHEQUE',      'چک'),
        ('POS',         'کارتخوان'),
        ('OTHER',       'سایر'),
    ]
    DEBT_PAYMENT_CHOICES = [
        ('CASH',        'نقدی'),
        ('CARD_TO_CARD','کارت به کارت'),
        ('CHEQUE',      'چک'),
        ('POS',         'کارتخوان'),
        ('COMBINED',    'ترکیبی'),
        ('OTHER',       'سایر'),
    ]

    id                     = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at             = models.DateTimeField(auto_now_add=True)
    branch                 = models.CharField(max_length=50, choices=BRANCH_CHOICES)
    created_by             = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='deposit_orders_created')
    seller                 = models.ForeignKey(Seller,     on_delete=models.PROTECT, related_name='deposit_orders')
    customer               = models.ForeignKey(Customer,   on_delete=models.PROTECT, related_name='deposit_orders')
    delivery_date          = models.DateField()
    total_amount           = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount        = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deposit_paid           = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    remaining_debt         = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    deposit_payment_method = models.CharField(max_length=30, choices=DEPOSIT_PAYMENT_CHOICES, blank=True, null=True)
    debt_payment_method    = models.CharField(max_length=30, choices=DEBT_PAYMENT_CHOICES,    blank=True, null=True)
    status                 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    sale                   = models.OneToOneField('Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='deposit_order')
    description            = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        net = (
            Decimal(str(self.total_amount))
            - Decimal(str(self.discount_amount))
            - Decimal(str(self.deposit_paid))
        )
        self.remaining_debt = max(Decimal('0.00'), net)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"بیعانه {self.customer.name} — {self.branch} — {self.created_at.date()}"


# ── DepositOrderItem ───────────────────────────────────────────────────────────
class DepositOrderItem(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    order       = models.ForeignKey(DepositOrder, on_delete=models.CASCADE, related_name='items')
    item_name   = models.CharField(max_length=150)
    quantity    = models.IntegerField()
    unit_price  = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total_price = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_name} × {self.quantity}"