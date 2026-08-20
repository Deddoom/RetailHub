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
ROLE_TREE: dict[str, set[str]] = {
    'ADMIN':             {'FINANCIAL_MANAGER', 'EXECUTIVE_MANAGER', 'SUPERVISOR',
                          'ACCOUNTANT', 'STATISTICIAN', 'CASHIER', 'USER',
                          'SALES_MANAGER', 'SELLER_STAFF', 'IRRIGATOR',
                          'GREEN_SPACE', 'ADVERTISING', 'WAREHOUSE'},
    'FINANCIAL_MANAGER': {'EXECUTIVE_MANAGER', 'SUPERVISOR',
                          'ACCOUNTANT', 'STATISTICIAN', 'CASHIER', 'USER',
                          'SALES_MANAGER', 'SELLER_STAFF', 'IRRIGATOR',
                          'GREEN_SPACE', 'ADVERTISING', 'WAREHOUSE'},
    'EXECUTIVE_MANAGER': {'SUPERVISOR', 'USER',
                          'SALES_MANAGER', 'SELLER_STAFF', 'IRRIGATOR',
                          'GREEN_SPACE', 'ADVERTISING'},
    'SUPERVISOR':        {'USER', 'SELLER_STAFF', 'IRRIGATOR', 'GREEN_SPACE', 'ADVERTISING'},
    'SALES_MANAGER':     {'SELLER_STAFF'},
    'ACCOUNTANT':        {'CASHIER', 'USER'},
    'STATISTICIAN':      set(),
    'CASHIER':           set(),
    'USER':              set(),
    'SELLER_STAFF':      set(),
    'IRRIGATOR':         set(),
    'GREEN_SPACE':       set(),
    'ADVERTISING':       set(),
    'WAREHOUSE':         set(),
}


def _get_all_subordinate_codes(role_codes: list[str]) -> set[str]:
    result: set[str] = set()
    queue  = list(role_codes)
    while queue:
        current  = queue.pop()
        children = ROLE_TREE.get(current, set())
        new      = children - result
        result  |= new
        queue.extend(new)
    return result


# ── Role ───────────────────────────────────────────────────────────────────────
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
        ('SALES_MANAGER',     'مدیر فروش'),
        ('SELLER_STAFF',      'فروشنده'),
        ('IRRIGATOR',         'آبیار'),
        ('GREEN_SPACE',       'نیرو فضای سبز'),
        ('ADVERTISING',       'نیرو تبلیغات'),
        ('WAREHOUSE',         'انباردار'),
    ]
    id   = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    code = models.CharField(max_length=30, choices=ROLE_CHOICES, unique=True)

    def __str__(self):
        return self.get_code_display()


# ── CustomUser ─────────────────────────────────────────────────────────────────
class CustomUser(AbstractUser):
    id     = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    roles  = models.ManyToManyField(Role, related_name='users', blank=True)
    branch = models.CharField(max_length=50, choices=BRANCH_CHOICES, blank=True, null=True)
    is_profile_completed = models.BooleanField(default=False)
    
    # ─── فیلد جدید برای تعریف افراد بالادستی ───
    superiors = models.ManyToManyField(
        'self', 
        symmetrical=False, 
        related_name='subordinate_users', 
        blank=True,
        help_text="افراد بالادستی مستقیم این کاربر"
    )

    groups           = models.ManyToManyField('auth.Group',      related_name='custom_users_groups',      blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='custom_users_permissions', blank=True)

    def __str__(self):
        if self.first_name or self.last_name:
            return f"{self.username} ({self.first_name} {self.last_name})".strip()
        roles_str = ", ".join([r.get_code_display() for r in self.roles.all()])
        return f"{self.username} ({roles_str})"

    def is_superior_to(self, target_user) -> bool:
        """
        بررسی سلسله‌مراتبی: آیا این کاربر (self) در درخت بالادستی‌های کاربر هدف (target_user) قرار دارد؟
        """
        if self.pk == target_user.pk:
            return False
            
        # ادمین کل به همه افراد دسترسی بالادستی دارد
        if self.is_superuser or any(r.code == 'ADMIN' for r in self.roles.all()):
            return True

        # جستجوی درختی (BFS) به سمت بالا برای یافتن این کاربر در بین مدیران
        visited = set()
        queue = [target_user]
        
        while queue:
            current = queue.pop(0)
            if current.pk in visited:
                continue
            visited.add(current.pk)
            
            # اگر کاربر فعلی (self) در لیست مدیران مستقیم گره در حال بررسی بود
            if self in current.superiors.all():
                return True
                
            # اضافه کردن مدیران گره فعلی به صف بررسی
            for sup in current.superiors.all():
                if sup.pk not in visited:
                    queue.append(sup)
                    
        return False

    def get_all_subordinates(self):
        """
        پیمایش بالا‌به‌پایین (BFS) برای یافتن تمام زیردستان یک کاربر.
        این متد از N+1 Query جلوگیری می‌کند.
        """
        subordinates = set()
        queue = list(self.subordinate_users.all())
        while queue:
            curr = queue.pop(0)
            if curr not in subordinates:
                subordinates.add(curr)
                queue.extend(curr.subordinate_users.all())
        return subordinates


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
    PAYMENT_METHOD_CHOICES = [
        ('CASH',         'نقدی'),
        ('CARD',         'کارتی'),
        ('CARD_TO_CARD', 'کارت به کارت'),
        ('POS',          'کارتخوان'),
        ('ACCOUNT',      'حساب به حساب'),
        ('TRANSFER',     'انتقال / حواله'),
        ('SHEBA',        'شبا'),
        ('CHEQUE',       'چکی'),
        ('COMBINED',     'ترکیبی'),
        ('DEPOSIT',      'بیعانه'),
        ('OTHER',        'سایر'),
    ]

    id                    = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name                  = models.CharField(max_length=150)
    phone                 = models.CharField(max_length=15, unique=True)
    address               = models.TextField(blank=True, null=True)
    purchase_types        = models.JSONField(default=list, help_text="لیست روش‌های پرداخت انتخابی")
    total_purchase_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    last_purchase_date    = models.DateField(auto_now_add=True)
    primary_goods         = models.CharField(max_length=50, choices=PRIMARY_GOODS_CHOICES, default='OTHER')
    buying_for            = models.CharField(max_length=50, choices=BUYING_FOR_CHOICES,    default='OTHER')
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
    id              = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    checklist       = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='tasks')
    title           = models.CharField(max_length=150)
    is_completed    = models.BooleanField(default=False)
    completed_by    = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at    = models.DateTimeField(null=True, blank=True)
    completion_note = models.TextField(
        blank=True, null=True,
        help_text="توضیح اختیاری که کاربر هنگام تیک زدن تسک وارد می‌کند"
    )
    description     = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title


# ── ChecklistLog ───────────────────────────────────────────────────────────────
class ChecklistLog(models.Model):
    FREQUENCY_CHOICES = [
        ('DAILY',   'روزانه'),
        ('WEEKLY',  'هفتگی'),
        ('MONTHLY', 'ماهانه'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    checklist           = models.ForeignKey(
        Checklist, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='logs'
    )
    checklist_title     = models.CharField(max_length=150)
    checklist_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)

    assigned_to          = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklist_logs_assigned'
    )
    assigned_to_username = models.CharField(max_length=150)

    created_by          = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklist_logs_created'
    )
    created_by_username = models.CharField(max_length=150)

    period_start = models.DateField(help_text="شروع دوره‌ای که این لاگ برای آن ثبت شده")
    period_end   = models.DateField(help_text="پایان دوره‌ای که این لاگ برای آن ثبت شده")

    logged_at = models.DateTimeField(auto_now_add=True)

    reset_by          = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklist_logs_reset'
    )
    reset_by_username = models.CharField(max_length=150, blank=True)

    total_tasks     = models.PositiveIntegerField(default=0)
    completed_tasks = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-logged_at']

    def __str__(self):
        return (
            f"[{self.checklist_frequency}] {self.checklist_title}"
            f" — {self.assigned_to_username}"
            f" — {self.period_start} تا {self.period_end}"
        )


# ── ChecklistLogItem ───────────────────────────────────────────────────────────
class ChecklistLogItem(models.Model):
    id  = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    log = models.ForeignKey(ChecklistLog, on_delete=models.CASCADE, related_name='items')

    task_title       = models.CharField(max_length=150)
    task_description = models.TextField(blank=True, null=True)

    is_completed    = models.BooleanField(default=False)
    completion_note = models.TextField(
        blank=True, null=True,
        help_text="یادداشتی که کاربر هنگام تیک زدن وارد کرده"
    )

    completed_by          = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklist_log_items_completed'
    )
    completed_by_username = models.CharField(max_length=150, blank=True)
    completed_at          = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['task_title']

    def __str__(self):
        status = "✓" if self.is_completed else "✗"
        return f"{status} {self.task_title}"


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
    
# ── Claim (مطالبه) ──────────────────────────────────────────────────────────────
class Claim(models.Model):
    STATUS_CHOICES = [
        ('UNPAID',      'پرداخت نشده'),
        ('IN_PROGRESS', 'در حال پیگیری'),
        ('NO_ANSWER',   'پاسخگو نیست'),
        ('REFUSED',     'عدم پرداخت'),
        ('PAID',        'پرداخت شده'),
    ]
    
    id                = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    customer_name     = models.CharField(max_length=150)
    customer_phone    = models.CharField(max_length=15)
    total_debt_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNPAID')
    taken_date        = models.DateField(help_text="زمان بردن اجناس")
    payment_deadline  = models.DateField(help_text="مهلت خواسته شده برای پرداخت")
    seller            = models.CharField(max_length=150)
    assigned_to       = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_claims')
    created_by        = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='created_claims')
    description       = models.TextField(blank=True, null=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"مطالبه {self.customer_name} - {self.get_status_display()}"


# ── ClaimItem (اجناس بدهکاری) ──────────────────────────────────────────────────
class ClaimItem(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    claim       = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='items')
    item_name   = models.CharField(max_length=150)
    quantity    = models.IntegerField()
    unit_price  = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total_price = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)


# ── ClaimFollowUp (پیگیری‌ها) ──────────────────────────────────────────────────
class ClaimFollowUp(models.Model):
    TYPE_CHOICES = [
        ('SMS',       'اس ام اسی'),
        ('PHONE',     'تلفنی'),
        ('IN_PERSON', 'حضوری'),
        ('OTHER',     'سایر'),
    ]
    id             = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    claim          = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='follow_ups')
    follower       = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='follow_ups_made')
    follow_up_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description    = models.TextField()
    date           = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"پیگیری {self.get_follow_up_type_display()} توسط {self.follower.username}"
    
# ── DamageRegistration (ثبت ضایعات) ──────────────────────────────────────────
class DamageRegistration(models.Model):
    REASON_CHOICES = [
        ('IRRIGATION', 'آبیاری'),
        ('PEST',       'آفت'),
        ('BREAKAGE',   'شکستگی'),
        ('LIGHT',      'نور'),
        ('OTHER',      'متفرقه'),
        ('UNKNOWN',    'نامعلوم'),
    ]
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    date        = models.DateField()
    branch      = models.CharField(max_length=50, choices=BRANCH_CHOICES)
    created_by  = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='damage_registrations')
    reason      = models.CharField(max_length=20, choices=REASON_CHOICES)
    culprit     = models.CharField(max_length=150, blank=True, null=True, help_text="مقصر")
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ضایعات {self.branch} - {self.date}"

class DamageItem(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    registration = models.ForeignKey(DamageRegistration, on_delete=models.CASCADE, related_name='items')
    item_name    = models.CharField(max_length=150)
    quantity     = models.IntegerField()
    unit_price   = models.DecimalField(max_digits=12, decimal_places=2)
    total_price  = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total_price = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)


# ── ReturnRequest (درخواست برگشتی کالا و وجه) ──────────────────────────────────
class ReturnRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING',   'در انتظار تایید مدیریت'),
        ('APPROVED',  'تایید شده (در انتظار واریز)'),
        ('COMPLETED', 'تکمیل شده (واریز شده)'),
        ('REJECTED',  'رد شده'),
    ]
    ACTION_CHOICES = [
        ('REFUND',   'فقط برگشت پول'),
        ('EXCHANGE', 'فقط تعویض کالا'),
        ('BOTH',     'هم برگشت پول هم تعویض کالا'),
    ]
    REFUND_METHOD_CHOICES = [
        ('CASH',         'نقدی'),
        ('CARD_TO_CARD', 'کارت به کارت'),
        ('ACCOUNT',      'حساب به حساب'),
        ('CHEQUE',       'چکی'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    customer_name  = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=15)
    seller         = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name='return_requests')
    created_by     = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='created_returns')
    
    action_type    = models.CharField(max_length=20, choices=ACTION_CHOICES)
    refund_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="مبلغ برگشتی به مشتری")
    
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_approved    = models.BooleanField(default=False)
    
    refund_date    = models.DateField(blank=True, null=True, help_text="تاریخ واریز وجه")
    refund_method  = models.CharField(max_length=30, choices=REFUND_METHOD_CHOICES, blank=True, null=True)
    
    description    = models.TextField(blank=True, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"برگشتی {self.customer_name} - {self.get_status_display()}"


class ReturnItem(models.Model):
    id             = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='return_items')
    item_name      = models.CharField(max_length=150)
    quantity       = models.IntegerField()
    unit_price     = models.DecimalField(max_digits=12, decimal_places=2)
    discount       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_price    = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total_price = (Decimal(str(self.quantity)) * Decimal(str(self.unit_price))) - Decimal(str(self.discount))
        super().save(*args, **kwargs)


class ExchangeItem(models.Model):
    id             = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='exchange_items')
    item_name      = models.CharField(max_length=150)
    quantity       = models.IntegerField()
    unit_price     = models.DecimalField(max_digits=12, decimal_places=2)
    total_price    = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        self.total_price = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
#  سیستم گزارش‌دهی (Report System)
# ══════════════════════════════════════════════════════════════════════════════

# ── ReportDefinition (تعریف گزارش توسط بالادستی) ──────────────────────────────
#
# فیلد questions:
#   لیستی از آبجکت‌ها با ساختار:
#   [{"id": "q1", "text": "متن سوال اول"}, {"id": "q2", "text": "متن سوال دوم"}]
#   - id: یک شناسه یکتا (مثلاً "q1", "q2") برای اتصال پاسخ به سوال
#   - text: متن سوال که به کاربر نمایش داده می‌شود
#
class ReportDefinition(models.Model):
    REPORT_TYPE_CHOICES = [
        ('RECURRING', 'تکراری'),
        ('DEADLINE',  'مهلت‌دار'),
    ]
    INTERVAL_CHOICES = [
        ('DAILY',      'روزانه'),
        ('WEEKLY',     'هفتگی'),
        ('MONTHLY',    'ماهانه'),
        ('BIMONTHLY',  'دو ماهه'),
        ('TRIMONTHLY', 'سه ماهه'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    superior    = models.ForeignKey(
        CustomUser, related_name='created_report_definitions',
        on_delete=models.CASCADE, verbose_name="بالادستی"
    )
    subordinate = models.ForeignKey(
        CustomUser, related_name='assigned_report_definitions',
        on_delete=models.CASCADE, verbose_name="زیردستی"
    )
    title       = models.CharField(max_length=255, verbose_name="عنوان کلی گزارش")
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, verbose_name="نوع گزارش")
    interval    = models.CharField(
        max_length=20, choices=INTERVAL_CHOICES,
        null=True, blank=True, verbose_name="دوره تکرار"
    )
    deadline    = models.DateTimeField(null=True, blank=True, verbose_name="مهلت انجام")

    # ساختار: [{"id": "q1", "text": "متن سوال"}, ...]
    questions   = models.JSONField(default=list, verbose_name="سوالات گزارش")

    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.subordinate.username}"


# ── ReportSubmission (ارسال گزارش توسط زیردستی) ────────────────────────────────
#
# فیلد answers:
#   لیستی از آبجکت‌ها با ساختار:
#   [{"question_id": "q1", "answer": "متن پاسخ"}, {"question_id": "q2", "answer": "متن پاسخ"}]
#   - question_id: باید با یکی از id های موجود در questions مطابقت داشته باشد
#   - answer: متن پاسخ کاربر
#
class ReportSubmission(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    definition   = models.ForeignKey(
        ReportDefinition, related_name='submissions',
        on_delete=models.CASCADE, verbose_name="تعریف گزارش"
    )
    submitted_by = models.ForeignKey(
        CustomUser, related_name='submitted_reports',
        on_delete=models.CASCADE, verbose_name="ارسال‌کننده"
    )

    # ساختار: [{"question_id": "q1", "answer": "پاسخ"}, ...]
    answers      = models.JSONField(default=list, verbose_name="پاسخ‌ها")

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"گزارش «{self.definition.title}» توسط {self.submitted_by.username}"


# ── ReportImage (عکس‌های ضمیمه گزارش) ─────────────────────────────────────────
class ReportImage(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    submission  = models.ForeignKey(
        ReportSubmission, related_name='images',
        on_delete=models.CASCADE, verbose_name="گزارش"
    )
    image_url   = models.URLField(max_length=500, verbose_name="آدرس تصویر")
    caption     = models.CharField(max_length=255, blank=True, null=True, verbose_name="توضیح تصویر")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"تصویر گزارش {self.submission_id}"
    
# ── BranchTransfer (انتقال بین شعب) ──────────────────────────────────────────
class BranchTransfer(models.Model):
    STATUS_CHOICES = [
        ('PENDING_SENDER',   'در انتظار تایید سرپرست مبدا'),
        ('PENDING_RECEIVER', 'در انتظار تایید سرپرست مقصد'),
        ('APPROVED',         'تایید نهایی'),
        ('REJECTED',         'رد شده'),
    ]
 
    id                  = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    source_cashier      = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT,
        related_name='initiated_transfers',
        verbose_name='صندوق‌دار مبدا (ثبت‌کننده)',
    )
    source_branch       = models.CharField(max_length=50, choices=BRANCH_CHOICES, verbose_name='شعبه مبدا')
    destination_branch  = models.CharField(max_length=50, choices=BRANCH_CHOICES, verbose_name='شعبه مقصد')
    sender_supervisor   = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT,
        related_name='sender_supervised_transfers',
        verbose_name='سرپرست فرستنده',
    )
    receiver_supervisor = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT,
        related_name='receiver_supervised_transfers',
        verbose_name='سرپرست گیرنده',
    )
    transfer_date       = models.DateField(verbose_name='تاریخ ارسال')
    driver_name         = models.CharField(max_length=150, verbose_name='نام راننده')
    description         = models.TextField(blank=True, null=True, verbose_name='توضیحات')
 
    # وضعیت و تاریخچه تصمیم‌ها
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_SENDER', verbose_name='وضعیت')
    rejection_reason = models.TextField(blank=True, null=True, verbose_name='دلیل عدم تایید')
    sender_note      = models.TextField(blank=True, null=True, verbose_name='توضیحات فرستنده هنگام تایید')
    receiver_note    = models.TextField(blank=True, null=True, verbose_name='توضیحات گیرنده هنگام تایید')
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ['-created_at']
 
    def __str__(self):
        return f"انتقال {self.source_branch} ← {self.destination_branch} ({self.get_status_display()})"
 
 
# ── TransferItem (اقلام انتقال) ───────────────────────────────────────────────
class TransferItem(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    transfer  = models.ForeignKey(BranchTransfer, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=150, verbose_name='نام جنس')
    quantity  = models.PositiveIntegerField(verbose_name='تعداد')
    price     = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='قیمت واحد')
 
    def __str__(self):
        return f"{self.item_name} × {self.quantity}"
 
 
# ── TransferLog (لاگ مراحل انتقال) ────────────────────────────────────────────
class TransferLog(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    transfer   = models.ForeignKey(BranchTransfer, on_delete=models.CASCADE, related_name='logs')
    message    = models.TextField(verbose_name='متن لاگ')
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='transfer_logs_created',
        verbose_name='کاربر ثبت‌کننده لاگ',
    )
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ['created_at']
 
    def __str__(self):
        return f"[{self.created_at.date()}] {self.message[:60]}"
 
 
# ── WasteReport (گزارش ضایعات) ────────────────────────────────────────────────
class WasteReport(models.Model):
    STATUS_CHOICES = [
        ('PENDING',               'در انتظار بررسی انباردار'),
        ('APPROVED_BY_WAREHOUSE', 'تایید انباردار — در انتظار مدیریت'),
        ('REJECTED_BY_WAREHOUSE', 'رد شده توسط انباردار'),
        ('CLOSED',                'تعیین تکلیف توسط مدیریت'),
    ]
 
    id         = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    reporter   = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT,
        related_name='reported_wastes',
        verbose_name='اعلام‌کننده (سرپرست)',
    )
    waste_date  = models.DateField(verbose_name='تاریخ ضایع شدن')
    branch      = models.CharField(max_length=50, choices=BRANCH_CHOICES, verbose_name='شعبه')
    description = models.TextField(blank=True, null=True, verbose_name='توضیحات')
 
    # افراد دخیل — چندین کاربر قابل انتخاب
    involved_users = models.ManyToManyField(
        CustomUser,
        related_name='involved_in_wastes',
        blank=True,
        verbose_name='افراد دخیل',
    )
 
    # مرحله انباردار
    status             = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING', verbose_name='وضعیت')
    warehouse_reviewer = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_wastes',
        verbose_name='انباردار بررسی‌کننده',
    )
    warehouse_comment  = models.TextField(blank=True, null=True, verbose_name='توضیحات انباردار')
 
    # مرحله مدیریت
    admin_reviewer    = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='admin_reviewed_wastes',
        verbose_name='مدیر تعیین‌تکلیف‌کننده',
    )
    admin_instruction = models.TextField(blank=True, null=True, verbose_name='دستور مدیریت')
 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ['-created_at']
 
    def __str__(self):
        return f"ضایعات {self.branch} — {self.waste_date} ({self.get_status_display()})"
 
 
# ── WasteItem (اقلام ضایعات) ──────────────────────────────────────────────────
class WasteItem(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    waste_report = models.ForeignKey(WasteReport, on_delete=models.CASCADE, related_name='items')
    item_name    = models.CharField(max_length=150, verbose_name='نام جنس')
    quantity     = models.PositiveIntegerField(verbose_name='تعداد')
    price        = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='قیمت واحد')
 
    def __str__(self):
        return f"{self.item_name} × {self.quantity}"

# ── UserOnlineLog (لاگ آنلاین شدن کاربران) ────────────────────────────────────
class UserOnlineLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='online_logs', verbose_name="کاربر"
    )
    date = models.DateField(verbose_name="تاریخ")
    first_seen = models.DateTimeField(auto_now_add=True, verbose_name="اولین بازدید روز")
    last_seen = models.DateTimeField(auto_now=True, verbose_name="آخرین بازدید روز")

    class Meta:
        unique_together = ('user', 'date') # هر کاربر در هر روز فقط یک رکورد دارد
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} - {self.date}"

# ── AdvanceRequest (درخواست مساعده) ──────────────────────────────────────────
class AdvanceRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING_SUPERIOR',     'در انتظار تایید بالادستی'),
        ('REJECTED_BY_SUPERIOR', 'رد شده توسط بالادستی'),
        ('PENDING_ADMIN',        'در انتظار تایید ادمین'),
        ('REJECTED_BY_ADMIN',    'رد شده توسط ادمین'),
        ('PENDING_FINANCE',      'در انتظار پرداخت (مدیر مالی)'),
        ('PAID',                 'پرداخت شده'),
    ]
    
    id          = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    requester   = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='advance_requests', verbose_name='درخواست‌کننده')
    amount      = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='مبلغ درخواستی')
    description = models.TextField(verbose_name='توضیحات کاربر')
    
    status      = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING_SUPERIOR', verbose_name='وضعیت')
    
    # مرحله بالادستی
    target_superior   = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_advance_requests', verbose_name='بالادستی انتخاب‌شده')
    superior_reviewer = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_advances_as_superior')
    superior_note     = models.TextField(blank=True, null=True, verbose_name='توضیحات بالادستی')
    
    # مرحله ادمین
    admin_reviewer    = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_advances_as_admin')
    admin_note        = models.TextField(blank=True, null=True, verbose_name='توضیحات ادمین')
    
    # مرحله مدیر مالی
    finance_reviewer  = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='paid_advances_as_finance')
    payment_date      = models.DateField(null=True, blank=True, verbose_name='تاریخ پرداخت')
    finance_note      = models.TextField(blank=True, null=True, verbose_name='توضیحات مدیر مالی')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"مساعده {self.amount} برای {self.requester.username} - {self.get_status_display()}"


# ── AdvanceRequestLog (لاگ مراحل مساعده) ──────────────────────────────────────
class AdvanceRequestLog(models.Model):
    id              = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    advance_request = models.ForeignKey(AdvanceRequest, on_delete=models.CASCADE, related_name='logs')
    actor           = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    action          = models.CharField(max_length=255, verbose_name='عملیات انجام شده')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']