"""
Migration 0010 — سیستم گزارش‌دهی

تغییرات:
  ۱. ReportDefinition — تعریف گزارش توسط بالادستی
  ۲. ReportSubmission — ارسال گزارش توسط زیردستی
  ۳. ReportImage      — تصاویر ضمیمه (با URLField بدون نیاز به Pillow)

نکته: اگر قبلاً مدل‌های Report با ImageField در دیتابیس ساخته شده‌اند،
      ابتدا باید جداول قدیمی را با SQL حذف کرد:
      DROP TABLE IF EXISTS core_reportimage CASCADE;
      DROP TABLE IF EXISTS core_reportsubmission CASCADE;
      DROP TABLE IF EXISTS core_reportdefinition CASCADE;
      DELETE FROM django_migrations WHERE name LIKE '%report%';
"""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_remove_customer_last_purchase_type_and_more'),
    ]

    operations = [

        # ─── ۱. ReportDefinition ───────────────────────────────────────────────
        migrations.CreateModel(
            name='ReportDefinition',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False
                )),
                ('title',       models.CharField(max_length=255, verbose_name='عنوان کلی گزارش')),
                ('report_type', models.CharField(
                    max_length=20,
                    choices=[('RECURRING', 'تکراری'), ('DEADLINE', 'مهلت‌دار')],
                    verbose_name='نوع گزارش'
                )),
                ('interval', models.CharField(
                    max_length=20, null=True, blank=True,
                    choices=[
                        ('WEEKLY',     'هفتگی'),
                        ('MONTHLY',    'ماهانه'),
                        ('BIMONTHLY',  'دو ماهه'),
                        ('TRIMONTHLY', 'سه ماهه'),
                    ],
                    verbose_name='دوره تکرار'
                )),
                ('deadline',   models.DateTimeField(null=True, blank=True, verbose_name='مهلت انجام')),
                ('questions',  models.JSONField(default=list, verbose_name='عناوین گزارش')),
                ('is_active',  models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('superior', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='created_report_definitions',
                    verbose_name='بالادستی'
                )),
                ('subordinate', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assigned_report_definitions',
                    verbose_name='زیردستی'
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ─── ۲. ReportSubmission ───────────────────────────────────────────────
        migrations.CreateModel(
            name='ReportSubmission',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False
                )),
                ('answers',      models.JSONField(default=dict, verbose_name='پاسخ‌ها')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('definition', models.ForeignKey(
                    to='core.ReportDefinition',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='submissions',
                    verbose_name='تعریف گزارش'
                )),
                ('submitted_by', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='submitted_reports',
                    verbose_name='ارسال‌کننده'
                )),
            ],
            options={'ordering': ['-submitted_at']},
        ),

        # ─── ۳. ReportImage ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='ReportImage',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False
                )),
                ('image_url',   models.URLField(max_length=500, verbose_name='آدرس تصویر')),
                ('caption',     models.CharField(max_length=255, blank=True, null=True, verbose_name='توضیح تصویر')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('submission', models.ForeignKey(
                    to='core.ReportSubmission',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='images',
                    verbose_name='گزارش'
                )),
            ],
            options={'ordering': ['uploaded_at']},
        ),
    ]
