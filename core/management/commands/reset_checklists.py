# core/management/commands/reset_checklists.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from core.models import Checklist, ChecklistLog, ChecklistLogItem, Task

class Command(BaseCommand):
    help = 'Snapshot and reset checklists based on frequency'

    def add_arguments(self, parser):
        parser.add_argument(
            '--frequency', 
            type=str, 
            required=True, 
            choices=['DAILY', 'WEEKLY', 'MONTHLY'],
            help='Frequency of checklists to reset'
        )

    def handle(self, *args, **options):
        freq = options['frequency']
        now = timezone.now()

        # محاسبه بازه زمانی حدودی برای لاگ (بر اساس فرکانس)
        period_end = now.date()
        if freq == 'DAILY':
            period_start = period_end - timedelta(days=1)
        elif freq == 'WEEKLY':
            period_start = period_end - timedelta(days=7)
        else: # MONTHLY
            period_start = period_end - timedelta(days=30)

        checklists = Checklist.objects.filter(frequency=freq).prefetch_related('tasks')
        
        if not checklists.exists():
            self.stdout.write(self.style.WARNING(f"No {freq} checklists found."))
            return

        with transaction.atomic():
            for cl in checklists:
                tasks = cl.tasks.all()
                total_tasks = tasks.count()
                completed_tasks = tasks.filter(is_completed=True).count()

                # 1. ساخت Snapshot در ChecklistLog
                log = ChecklistLog.objects.create(
                    checklist=cl,
                    checklist_title=cl.title,
                    checklist_frequency=cl.frequency,
                    assigned_to=cl.assigned_to,
                    assigned_to_username=cl.assigned_to.username if cl.assigned_to else "بدون مسئول",
                    created_by=cl.created_by,
                    created_by_username=cl.created_by.username if cl.created_by else "نامشخص",
                    period_start=period_start,
                    period_end=period_end,
                    total_tasks=total_tasks,
                    completed_tasks=completed_tasks
                )

                # 2. کپی Task ها به عنوان ChecklistLogItem و ریست کردن Task اصلی
                items_to_create = []
                for task in tasks:
                    # آماده‌سازی آیتم لاگ
                    items_to_create.append(ChecklistLogItem(
                        log=log,
                        task_title=task.title,
                        task_description=task.description,
                        is_completed=task.is_completed,
                        completion_note=task.completion_note,
                        completed_by=task.completed_by,
                        completed_by_username=task.completed_by.username if task.completed_by else "",
                        completed_at=task.completed_at
                    ))

                    # ریست کردن تسک برای دوره جدید
                    task.is_completed = False
                    task.completed_by = None
                    task.completed_at = None
                    task.completion_note = None
                    task.save()

                # ذخیره گروهی آیتم‌های لاگ برای پرفورمنس بهتر
                ChecklistLogItem.objects.bulk_create(items_to_create)

        self.stdout.write(self.style.SUCCESS(f"Successfully reset {checklists.count()} {freq} checklists."))