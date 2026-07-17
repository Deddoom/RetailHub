"""
Migration 0012 — نقش‌های جدید و اصلاح ساختار گزارش‌دهی

تغییرات:
  ۱. اضافه کردن ۵ نقش جدید به مدل Role:
     - SALES_MANAGER  (مدیر فروش)
     - SELLER_STAFF   (فروشنده)
     - IRRIGATOR      (آبیار)
     - GREEN_SPACE    (نیرو فضای سبز)
     - ADVERTISING    (نیرو تبلیغات)

  ۲. تغییر نوع فیلد answers در ReportSubmission:
     از: JSONField(default=dict) — دیکشنری {"سوال": "پاسخ"}
     به: JSONField(default=list) — لیست [{"question_id": "q1", "answer": "پاسخ"}]

     نکته: چون دیتای قدیمی در دیتابیس ممکن است dict باشد،
     یک data migration هم اجرا می‌کنیم.

  ۳. اصلاح comment داخل model برای وضوح ساختار questions.
"""
from django.db import migrations, models
import json


def migrate_answers_to_list(apps, schema_editor):
    """
    مقادیر قدیمی answers که به صورت dict بودند را به list تبدیل می‌کند.
    ساختار قدیمی: {"سوال اول": "پاسخ"}
    ساختار جدید:  [{"question_id": "q1", "answer": "پاسخ"}]
    """
    ReportSubmission = apps.get_model('core', 'ReportSubmission')

    for submission in ReportSubmission.objects.all():
        answers = submission.answers

        # اگر از قبل list است، نیازی به تبدیل نیست
        if isinstance(answers, list):
            continue

        # اگر dict است، تبدیل می‌کنیم
        if isinstance(answers, dict):
            new_answers = []
            for idx, (question_text, answer_text) in enumerate(answers.items(), start=1):
                new_answers.append({
                    "question_id": f"q{idx}",
                    "answer": str(answer_text)
                })
            submission.answers = new_answers
            submission.save(update_fields=['answers'])

        # اگر string یا چیز دیگری بود، لیست خالی می‌گذاریم
        elif not isinstance(answers, (list, dict)):
            submission.answers = []
            submission.save(update_fields=['answers'])


def reverse_answers_to_dict(apps, schema_editor):
    """
    برگشت به ساختار dict — فقط برای rollback اضطراری.
    """
    ReportSubmission = apps.get_model('core', 'ReportSubmission')

    for submission in ReportSubmission.objects.all():
        answers = submission.answers

        if isinstance(answers, list):
            old_dict = {}
            for item in answers:
                if isinstance(item, dict):
                    qid    = item.get('question_id', '')
                    answer = item.get('answer', '')
                    old_dict[qid] = answer
            submission.answers = old_dict
            submission.save(update_fields=['answers'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_fix_customer_decimal'),
    ]

    operations = [

        # ─── ۱. اضافه کردن نقش‌های جدید به choices فیلد Role.code ─────────────
        # (choices در Django فقط سطح Python است، نیازی به تغییر schema ندارد)
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
                ],
            ),
        ),

        # ─── ۲. data migration: تبدیل answers از dict به list ────────────────
        migrations.RunPython(
            migrate_answers_to_list,
            reverse_code=reverse_answers_to_dict,
        ),

        # ─── ۳. تغییر default فیلد answers از dict به list ───────────────────
        migrations.AlterField(
            model_name='reportsubmission',
            name='answers',
            field=models.JSONField(
                default=list,
                verbose_name='پاسخ‌ها',
                help_text='ساختار: [{"question_id": "q1", "answer": "متن پاسخ"}, ...]'
            ),
        ),
    ]
