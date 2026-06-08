# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import AbstractUser
from uuid import uuid4
from decimal import Decimal

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'مدیر سیستم (Admin)'),
        ('CASHIER', 'صندوق‌دار (Cashier)'),
        ('USER', 'کارکنان عادی (User)'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USER')
    branch = models.CharField(max_length=100, blank=True, null=True)

    groups = models.ManyToManyField('auth.Group', related_name='custom_users_groups', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='custom_users_permissions', blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Seller(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15, unique=True, blank=True, null=True)
    branch = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} - {self.branch}"


class Customer(models.Model):
    PRIMARY_GOODS_CHOICES = [
        ('APARTMENT', 'آپارتمانی'), ('OUTDOOR', 'بیرونی'), ('FERTILIZER', 'کود'),
        ('NEHAL', 'نهال'), ('POT', 'گلدان'), ('OTHER', 'متفرقه'),
    ]
    BUYING_FOR_CHOICES = [
        ('GARDEN', 'باغ'), ('HOUSE', 'خانه'), ('SHOP', 'مغازه'), ('OTHER', 'متفرقه'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    primary_goods = models.CharField(max_length=50, choices=PRIMARY_GOODS_CHOICES, default='OTHER')
    buying_for = models.CharField(max_length=50, choices=BUYING_FOR_CHOICES, default='OTHER')

    last_purchase_date = models.DateField(blank=True, null=True)
    total_purchase_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    last_purchase_type = models.CharField(max_length=30, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Sale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date_time = models.DateTimeField(auto_now_add=True)
    branch = models.CharField(max_length=100)
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name='sales')
    # تغییر ۲: customer اختیاری شد — می‌توان فاکتور بدون مشتری ثبت کرد
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name='sales',
        blank=True, null=True
    )
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='sales_created')
    description = models.TextField(blank=True, null=True)


class Payment(models.Model):
    METHOD_CHOICES = [
        ('CASH', 'نقدی'), ('CARD_TO_CARD', 'کارت به کارت'), ('SHEBA', 'شبا'),
        ('POS', 'کارتخوان'), ('COMBINED', 'ترکیبی'), ('REMAINING', 'وجه مانده'),
        ('DEPOSIT', 'بیعانه'), ('CHEQUE', 'چک صیادی/عادی'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, null=True)


class Expense(models.Model):
    METHOD_CHOICES = [
        ('CASH', 'نقدی'), ('CARD', 'کارتی'), ('ACCOUNT_TO_ACCOUNT', 'حساب به حساب'),
        ('COMBINED', 'ترکیبی'), ('CHEQUE', 'چکی'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    date = models.DateField()
    category = models.CharField(max_length=100)
    branch = models.CharField(max_length=100)
    invoice_image_url = models.URLField(max_length=500, blank=True, null=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='expenses_created')
    description = models.TextField(blank=True, null=True)


class Cheque(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='cheques', blank=True, null=True)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='cheques', blank=True, null=True)
    due_date = models.DateField()
    cheque_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    customer_phone = models.CharField(max_length=15, blank=True, null=True)
    customer_name = models.CharField(max_length=150, blank=True, null=True)
    is_endorsed = models.BooleanField(default=False)
    # تغییر ۴: فیلد جدید برای ذخیره عکس چک — اختیاری
    cheque_image_url = models.URLField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True, null=True)


class DepositItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='deposit_items')
    item_name = models.CharField(max_length=150)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)


class DamageReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    item_name = models.CharField(max_length=150)
    quantity = models.IntegerField()
    estimated_loss = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    branch = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT)


class ItemExit(models.Model):
    REASON_CHOICES = [('RETURN', 'مرجوعی به تامین‌کننده'), ('DAMAGE', 'خرابی و ضایعات'), ('INTERNAL', 'مصرف داخلی')]
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    item_name = models.CharField(max_length=150)
    quantity = models.IntegerField()
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    date = models.DateField()
    branch = models.CharField(max_length=100)
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT)


class Checklist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    title = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT)


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=150)
    is_completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)