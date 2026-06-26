"""
Migration 0005 — اضافه کردن سیستم لاگ چک‌لیست

تغییرات:
  ۱. اضافه کردن فیلد completion_note به مدل Task
  ۲. ساخت مدل ChecklistLog (snapshot غیرقابل‌تغییر دوره)
  ۳. ساخت مدل ChecklistLogItem (آیتم‌های هر snapshot)
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        # آخرین migration موجود در پروژه
        ('core', '0004_role_mission_checklist_update'),
    ]

    operations = [

        # ─── ۱. اضافه کردن completion_note به Task ────────────────────────────
        migrations.AddField(
            model_name='task',
            name='completion_note',
            field=models.TextField(
                blank=True, null=True,
                help_text='توضیح اختیاری که کاربر هنگام تیک زدن تسک وارد می‌کند'
            ),
        ),

        # ─── ۲. ساخت مدل ChecklistLog ─────────────────────────────────────────
        migrations.CreateModel(
            name='ChecklistLog',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False
                )),
                ('checklist_title', models.CharField(max_length=150)),
                ('checklist_frequency', models.CharField(
                    max_length=20,
                    choices=[
                        ('DAILY',   'روزانه'),
                        ('WEEKLY',  'هفتگی'),
                        ('MONTHLY', 'ماهانه'),
                    ]
                )),
                ('assigned_to_username', models.CharField(max_length=150)),
                ('created_by_username',  models.CharField(max_length=150)),
                ('period_start', models.DateField(
                    help_text='شروع دوره‌ای که این لاگ برای آن ثبت شده'
                )),
                ('period_end', models.DateField(
                    help_text='پایان دوره‌ای که این لاگ برای آن ثبت شده'
                )),
                ('logged_at', models.DateTimeField(auto_now_add=True)),
                ('reset_by_username', models.CharField(max_length=150, blank=True)),
                ('total_tasks',     models.PositiveIntegerField(default=0)),
                ('completed_tasks', models.PositiveIntegerField(default=0)),

                # FK‌های nullable (تا بعد از حذف کاربر/چک‌لیست هم بماند)
                ('checklist', models.ForeignKey(
                    to='core.Checklist',
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='logs',
                )),
                ('assigned_to', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='checklist_logs_assigned',
                )),
                ('created_by', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='checklist_logs_created',
                )),
                ('reset_by', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='checklist_logs_reset',
                )),
            ],
            options={
                'ordering': ['-logged_at'],
            },
        ),

        # ─── ۳. ساخت مدل ChecklistLogItem ──────────────────────────────────────
        migrations.CreateModel(
            name='ChecklistLogItem',
            fields=[
                ('id', models.UUIDField(
                    default=uuid.uuid4, editable=False,
                    primary_key=True, serialize=False
                )),
                ('task_title',       models.CharField(max_length=150)),
                ('task_description', models.TextField(blank=True, null=True)),
                ('is_completed',     models.BooleanField(default=False)),
                ('completion_note',  models.TextField(
                    blank=True, null=True,
                    help_text='یادداشتی که کاربر هنگام تیک زدن وارد کرده'
                )),
                ('completed_by_username', models.CharField(max_length=150, blank=True)),
                ('completed_at',          models.DateTimeField(null=True, blank=True)),

                ('log', models.ForeignKey(
                    to='core.ChecklistLog',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                )),
                ('completed_by', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='checklist_log_items_completed',
                )),
            ],
            options={
                'ordering': ['task_title'],
            },
        ),
    ]
