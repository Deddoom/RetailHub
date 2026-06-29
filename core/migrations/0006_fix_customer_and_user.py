"""
Migration 0006 — رفع باگ‌های migration

تغییرات:
  ۱. اضافه کردن is_profile_completed به CustomUser
  ۲. اضافه کردن purchase_types (JSONField) به Customer
  ۳. حذف last_purchase_type از Customer
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_checklist_log_system'),
    ]

    operations = [
        # ── ۱. اضافه کردن is_profile_completed به CustomUser ─────────────────
        migrations.AddField(
            model_name='customuser',
            name='is_profile_completed',
            field=models.BooleanField(default=False),
        ),

        # ── ۲. اضافه کردن purchase_types به Customer ─────────────────────────
        migrations.AddField(
            model_name='customer',
            name='purchase_types',
            field=models.JSONField(
                default=list,
                help_text='لیست روش‌های پرداخت انتخابی'
            ),
        ),

        # ── ۳. حذف last_purchase_type از Customer ────────────────────────────
        migrations.RemoveField(
            model_name='customer',
            name='last_purchase_type',
        ),
    ]
