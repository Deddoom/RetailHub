from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_depositorder_depositorderitem'),
    ]

    operations = [
        # ساخت مدل Role
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('code', models.CharField(max_length=30, unique=True, choices=[
                    ('ADMIN', 'مدیریت (Admin)'),
                    ('FINANCIAL_MANAGER', 'مدیر مالی'),
                    ('EXECUTIVE_MANAGER', 'مدیر اجرایی'),
                    ('SUPERVISOR', 'سرپرست'),
                    ('ACCOUNTANT', 'حسابدار'),
                    ('STATISTICIAN', 'آمارگیر'),
                    ('CASHIER', 'صندوق‌دار'),
                    ('USER', 'کارکنان عادی'),
                ])),
            ],
        ),
        # اضافه کردن roles به CustomUser
        migrations.AddField(
            model_name='customuser',
            name='roles',
            field=models.ManyToManyField(to='core.Role', related_name='users', blank=True),
        ),
        # حذف فیلد role قدیمی از CustomUser
        migrations.RemoveField(model_name='customuser', name='role'),
        # اصلاح branch در CustomUser
        migrations.AlterField(
            model_name='customuser',
            name='branch',
            field=models.CharField(max_length=50, choices=[
                ('شعبه بهشتی', 'شعبه بهشتی'),
                ('شعبه مدرس', 'شعبه مدرس'),
                ('شعبه سپیده', 'شعبه سپیده'),
                ('شعبه کاجستان', 'شعبه کاجستان'),
            ], blank=True, null=True),
        ),
        # ساخت مدل Mission
        migrations.CreateModel(
            name='Mission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('title', models.CharField(max_length=150)),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField()),
                ('status', models.CharField(max_length=20, default='PENDING', choices=[
                    ('PENDING', 'در انتظار انجام'),
                    ('DOING', 'در حال انجام'),
                    ('COMPLETED', 'انجام شده'),
                    ('CANCELLED', 'لغو شده'),
                ])),
                ('description', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE,
                    related_name='missions'
                )),
                ('created_by', models.ForeignKey(
                    settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    related_name='created_missions'
                )),
            ],
        ),
        # اصلاح Checklist — اضافه کردن assigned_to و frequency
        migrations.AddField(
            model_name='checklist',
            name='frequency',
            field=models.CharField(max_length=20, default='DAILY', choices=[
                ('DAILY', 'روزانه'), ('WEEKLY', 'هفتگی'), ('MONTHLY', 'ماهانه')
            ]),
        ),
        migrations.AddField(
            model_name='checklist',
            name='assigned_to',
            field=models.ForeignKey(
                settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE,
                related_name='assigned_checklists',
                null=True,
            ),
        ),
    ]
