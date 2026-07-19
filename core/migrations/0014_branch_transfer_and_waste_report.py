"""
Migration 0014 — انتقال بین شعب و ضایعات

تغییرات:
  ۱. اضافه کردن نقش WAREHOUSE به Role.code choices
  ۲. ساخت مدل BranchTransfer (انتقال بین شعب)
  ۳. ساخت مدل TransferItem (اقلام انتقال)
  ۴. ساخت مدل TransferLog (لاگ مراحل انتقال)
  ۵. ساخت مدل WasteReport (گزارش ضایعات — جایگزین DamageRegistration)
  ۶. ساخت مدل WasteItem (اقلام ضایعات)
"""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        # هر دو branch را به عنوان dependency معرفی می‌کنیم
        ('core', '0012_new_roles_and_report_answers'),
        ('core', '0013_alter_reportdefinition_questions_and_more'),
    ]

    operations = [

        # ─── ۱. اضافه کردن WAREHOUSE به choices نقش‌ها ──────────────────────
        migrations.AlterField(
            model_name='role',
            name='code',
            field=models.CharField(
                max_length=30,
                unique=True,
                choices=[
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
                ],
            ),
        ),

        # ─── ۲. BranchTransfer ───────────────────────────────────────────────
        migrations.CreateModel(
            name='BranchTransfer',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False,
                )),
                ('source_branch', models.CharField(
                    max_length=50,
                    choices=[
                        ('شعبه بهشتی',  'شعبه بهشتی'),
                        ('شعبه مدرس',   'شعبه مدرس'),
                        ('شعبه سپیده',  'شعبه سپیده'),
                        ('شعبه کاجستان','شعبه کاجستان'),
                    ],
                    verbose_name='شعبه مبدا',
                )),
                ('destination_branch', models.CharField(
                    max_length=50,
                    choices=[
                        ('شعبه بهشتی',  'شعبه بهشتی'),
                        ('شعبه مدرس',   'شعبه مدرس'),
                        ('شعبه سپیده',  'شعبه سپیده'),
                        ('شعبه کاجستان','شعبه کاجستان'),
                    ],
                    verbose_name='شعبه مقصد',
                )),
                ('transfer_date', models.DateField(verbose_name='تاریخ ارسال')),
                ('driver_name', models.CharField(max_length=150, verbose_name='نام راننده')),
                ('description', models.TextField(blank=True, null=True, verbose_name='توضیحات')),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('PENDING_SENDER',   'در انتظار تایید سرپرست مبدا'),
                        ('PENDING_RECEIVER', 'در انتظار تایید سرپرست مقصد'),
                        ('APPROVED',         'تایید نهایی'),
                        ('REJECTED',         'رد شده'),
                    ],
                    default='PENDING_SENDER',
                    verbose_name='وضعیت',
                )),
                ('rejection_reason', models.TextField(blank=True, null=True, verbose_name='دلیل عدم تایید')),
                ('sender_note', models.TextField(blank=True, null=True, verbose_name='توضیحات فرستنده هنگام تایید')),
                ('receiver_note', models.TextField(blank=True, null=True, verbose_name='توضیحات گیرنده هنگام تایید')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_cashier', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='initiated_transfers',
                    verbose_name='صندوق‌دار مبدا (ثبت‌کننده)',
                )),
                ('sender_supervisor', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='sender_supervised_transfers',
                    verbose_name='سرپرست فرستنده',
                )),
                ('receiver_supervisor', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='receiver_supervised_transfers',
                    verbose_name='سرپرست گیرنده',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ─── ۳. TransferItem ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='TransferItem',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False,
                )),
                ('item_name', models.CharField(max_length=150, verbose_name='نام جنس')),
                ('quantity',  models.PositiveIntegerField(verbose_name='تعداد')),
                ('price', models.DecimalField(max_digits=12, decimal_places=2, verbose_name='قیمت واحد')),
                ('transfer', models.ForeignKey(
                    to='core.BranchTransfer',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                )),
            ],
        ),

        # ─── ۴. TransferLog ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='TransferLog',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False,
                )),
                ('message',    models.TextField(verbose_name='متن لاگ')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='transfer_logs_created',
                    verbose_name='کاربر ثبت‌کننده لاگ',
                )),
                ('transfer', models.ForeignKey(
                    to='core.BranchTransfer',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='logs',
                )),
            ],
            options={'ordering': ['created_at']},
        ),

        # ─── ۵. WasteReport ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='WasteReport',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False,
                )),
                ('waste_date',  models.DateField(verbose_name='تاریخ ضایع شدن')),
                ('branch', models.CharField(
                    max_length=50,
                    choices=[
                        ('شعبه بهشتی',  'شعبه بهشتی'),
                        ('شعبه مدرس',   'شعبه مدرس'),
                        ('شعبه سپیده',  'شعبه سپیده'),
                        ('شعبه کاجستان','شعبه کاجستان'),
                    ],
                    verbose_name='شعبه',
                )),
                ('description', models.TextField(blank=True, null=True, verbose_name='توضیحات')),
                ('status', models.CharField(
                    max_length=30,
                    choices=[
                        ('PENDING',               'در انتظار بررسی انباردار'),
                        ('APPROVED_BY_WAREHOUSE', 'تایید انباردار — در انتظار مدیریت'),
                        ('REJECTED_BY_WAREHOUSE', 'رد شده توسط انباردار'),
                        ('CLOSED',                'تعیین تکلیف توسط مدیریت'),
                    ],
                    default='PENDING',
                    verbose_name='وضعیت',
                )),
                ('warehouse_comment',  models.TextField(blank=True, null=True, verbose_name='توضیحات انباردار')),
                ('admin_instruction',  models.TextField(blank=True, null=True, verbose_name='دستور مدیریت')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reporter', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='reported_wastes',
                    verbose_name='اعلام‌کننده (سرپرست)',
                )),
                ('warehouse_reviewer', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='reviewed_wastes',
                    verbose_name='انباردار بررسی‌کننده',
                )),
                ('admin_reviewer', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='admin_reviewed_wastes',
                    verbose_name='مدیر تعیین‌تکلیف‌کننده',
                )),
                ('involved_users', models.ManyToManyField(
                    to=settings.AUTH_USER_MODEL,
                    related_name='involved_in_wastes',
                    blank=True,
                    verbose_name='افراد دخیل',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ─── ۶. WasteItem ────────────────────────────────────────────────────
        migrations.CreateModel(
            name='WasteItem',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False,
                )),
                ('item_name', models.CharField(max_length=150, verbose_name='نام جنس')),
                ('quantity',  models.PositiveIntegerField(verbose_name='تعداد')),
                ('price', models.DecimalField(max_digits=12, decimal_places=2, verbose_name='قیمت واحد')),
                ('waste_report', models.ForeignKey(
                    to='core.WasteReport',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                )),
            ],
        ),
    ]
