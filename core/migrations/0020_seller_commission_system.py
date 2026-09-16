# -*- coding: utf-8 -*-
from decimal import Decimal
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_alter_advancerequest_target_superior'),
    ]

    operations = [
        migrations.CreateModel(
            name='SellerCommissionConfig',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال است؟')),
                ('model_type', models.CharField(choices=[('THRESHOLD_SURPLUS', 'کف و درصد مازاد'), ('TIERED_FROM_BASE', 'پورسانت پلکانی از کف')], default='THRESHOLD_SURPLUS', max_length=30, verbose_name='نوع مدل پورسانت')),
                ('threshold_amount', models.DecimalField(blank=True, decimal_places=2, default=Decimal('0.00'), max_digits=14, null=True, verbose_name='مبلغ کف فروش')),
                ('surplus_percentage', models.DecimalField(blank=True, decimal_places=2, default=Decimal('0.00'), max_digits=5, null=True, verbose_name='درصد مازاد بر کف')),
                ('tiers', models.JSONField(blank=True, default=list, verbose_name='پلکان\u200cهای پورسانت')),
                ('reward_active', models.BooleanField(default=False, verbose_name='سیستم پاداش فعال است؟')),
                ('reward_mode', models.CharField(choices=[('HIGHEST_ONLY', 'فقط بالاترین تارگت'), ('CUMULATIVE', 'تجمعی پله\u200cها')], default='HIGHEST_ONLY', max_length=20, verbose_name='نحوه محاسبه پاداش')),
                ('reward_milestones', models.JSONField(blank=True, default=list, verbose_name='تارگت\u200cهای پاداش')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_commission_configs', to=settings.AUTH_USER_MODEL, verbose_name='ثبت\u200cکننده')),
                ('seller', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='commission_config', to=settings.AUTH_USER_MODEL, verbose_name='فروشنده')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_commission_configs', to=settings.AUTH_USER_MODEL, verbose_name='آخرین ویرایش\u200cکننده')),
            ],
            options={
                'verbose_name': 'تنظیمات پورسانت فروشنده',
                'verbose_name_plural': 'تنظیمات پورسانت فروشندگان',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SellerDailySale',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('shamsi_year', models.PositiveSmallIntegerField(db_index=True, verbose_name='سال شمسی')),
                ('shamsi_month', models.PositiveSmallIntegerField(db_index=True, verbose_name='ماه شمسی')),
                ('shamsi_day', models.PositiveSmallIntegerField(verbose_name='روز ماه شمسی')),
                ('date', models.DateField(blank=True, db_index=True, null=True, verbose_name='تاریخ میلادی معادل')),
                ('amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='مبلغ فروش روز')),
                ('branch', models.CharField(choices=[('شعبه بهشتی', 'شعبه بهشتی'), ('شعبه مدرس', 'شعبه مدرس'), ('شعبه سپیده', 'شعبه سپیده'), ('شعبه کاجستان', 'شعبه کاجستان')], max_length=50, verbose_name='شعبه')),
                ('notes', models.CharField(blank=True, max_length=255, null=True, verbose_name='یادداشت')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_daily_sales', to=settings.AUTH_USER_MODEL, verbose_name='صندوق\u200cدار ثبت\u200cکننده')),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_sales', to=settings.AUTH_USER_MODEL, verbose_name='فروشنده')),
            ],
            options={
                'verbose_name': 'فروش روزانه فروشنده',
                'verbose_name_plural': 'فروش\u200cهای روزانه فروشندگان',
                'ordering': ['shamsi_year', 'shamsi_month', 'shamsi_day'],
                'unique_together': {('seller', 'shamsi_year', 'shamsi_month', 'shamsi_day')},
            },
        ),
    ]
