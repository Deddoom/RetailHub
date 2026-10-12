# -*- coding: utf-8 -*-
from django.test import TestCase
from decimal import Decimal
import datetime
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from core.models import (
    LiquidityDailyRevenueSetting,
    LiquidityExpense,
    LiquidityDailyCharge,
    LiquidityCheck,
    Role,
)

User = get_user_model()


class LiquidityChecksAndChargesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='admin_user',
            password='Password123!',
            first_name='مدیر',
            last_name='سیستم',
            is_superuser=True
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.today = datetime.date.today()

    def test_daily_charge_subfields_and_total_calculation(self):
        """تست ثبت شارژ روزانه با تفکیک شعب و محاسبه خودکار مجموع کل"""
        past_date = self.today - datetime.timedelta(days=2)
        payload = {
            'date': str(past_date),
            'beheshti_pos': 10000000,
            'beheshti_cash': 2000000,
            'beheshti_card_to_card': 3000000,  # مجموع بهشتی: ۱۵ میلیون
            'sepideh_pos': 5000000,
            'sepideh_cash': 1000000,
            'sepideh_card_to_card': 2000000,   # مجموع سپیده: ۸ میلیون
            'modarres_pos': 7000000,
            'modarres_cash': 3000000,
            'modarres_card_to_card': 0,        # مجموع مدرس: ۱۰ میلیون
            'kajestan_pos': 4000000,
            'kajestan_cash': 1000000,
            'kajestan_card_to_card': 1000000,  # مجموع کاجستان: ۶ میلیون
            'debt_collection': 5000000,         # وصول مطالبات: ۵ میلیون
            'passed_checks_amount': 8000000,    # چک پاس شده: ۸ میلیون
            'description': 'شارژ با تفکیک کامل شعب دو روز قبل'
        }
        # جمع کل: 15 + 8 + 10 + 6 + 5 + 8 = 52,000,000

        res = self.client.post('/api/liquidity/daily-charges/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.data
        self.assertEqual(data['date'], str(past_date))
        self.assertIsNotNone(data['date_jalali'])
        self.assertEqual(Decimal(str(data['beheshti_total'])), Decimal('15000000.00'))
        self.assertEqual(Decimal(str(data['sepideh_total'])), Decimal('8000000.00'))
        self.assertEqual(Decimal(str(data['modarres_total'])), Decimal('10000000.00'))
        self.assertEqual(Decimal(str(data['kajestan_total'])), Decimal('6000000.00'))
        self.assertEqual(Decimal(str(data['branch_sales_total'])), Decimal('39000000.00'))
        self.assertEqual(Decimal(str(data['total_sales'])), Decimal('52000000.00'))
        self.assertEqual(Decimal(str(data['amount'])), Decimal('52000000.00'))

    def test_daily_charge_legacy_amount_compatibility(self):
        """تست سازگاری با رکوردهای بدون تفکیک شعب (ارسال فقط amount)"""
        payload = {
            'amount': 25000000,
            'description': 'شارژ سنتی بدون تفکیک شعب'
        }
        res = self.client.post('/api/liquidity/daily-charges/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(str(res.data['amount'])), Decimal('25000000.00'))
        self.assertEqual(res.data['date'], str(self.today))

    def test_daily_charge_date_filter(self):
        """تست فیلتر تاریخ از و تا روی شارژهای روزانه"""
        d1 = self.today - datetime.timedelta(days=5)
        d2 = self.today - datetime.timedelta(days=1)
        LiquidityDailyCharge.objects.create(date=d1, amount=Decimal('10000000'), created_by=self.user)
        LiquidityDailyCharge.objects.create(date=d2, amount=Decimal('20000000'), created_by=self.user)

        res = self.client.get(f'/api/liquidity/daily-charges/?from_date={d2}&to_date={self.today}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # فقط رکورد دوم باید برگردد
        dates = [item['date'] for item in res.data]
        self.assertIn(str(d2), dates)
        self.assertNotIn(str(d1), dates)

    def test_check_creation_and_auto_overdue_transition(self):
        """تست ثبت چک و انتقال خودکار چک‌های سررسید گذشته از PENDING به UNPAID"""
        future_due = self.today + datetime.timedelta(days=10)
        past_due = self.today - datetime.timedelta(days=3)

        chk_future = LiquidityCheck.objects.create(
            customer_name='آقای رضایی',
            due_date=future_due,
            amount=Decimal('15000000.00'),
            branch='BEHESHTI',
            status='PENDING',
            created_by=self.user
        )

        chk_past = LiquidityCheck.objects.create(
            customer_name='شرکت امید',
            due_date=past_due,
            amount=Decimal('30000000.00'),
            branch='MODARRES',
            status='PENDING',
            created_by=self.user
        )

        # فراخوانی لیست چک‌ها
        res = self.client.get('/api/liquidity/checks/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        chk_future.refresh_from_db()
        chk_past.refresh_from_db()

        # چک آینده باید همچنان PENDING بماند
        self.assertEqual(chk_future.status, 'PENDING')
        # چک گذشته باید خودکار به UNPAID (عدم پرداخت) تبدیل شده باشد
        self.assertEqual(chk_past.status, 'UNPAID')

    def test_checks_summary_endpoint(self):
        """تست اندپوینت آمار و شمارش وضعیت‌های چک‌ها"""
        LiquidityCheck.objects.create(
            customer_name='مشتری ۱', due_date=self.today + datetime.timedelta(days=5),
            amount=Decimal('10000000.00'), status='CLEARED', created_by=self.user
        )
        LiquidityCheck.objects.create(
            customer_name='مشتری ۲', due_date=self.today + datetime.timedelta(days=5),
            amount=Decimal('20000000.00'), status='PENDING', created_by=self.user
        )
        LiquidityCheck.objects.create(
            customer_name='مشتری ۳', due_date=self.today - datetime.timedelta(days=2),
            amount=Decimal('15000000.00'), status='PENDING', created_by=self.user  # این تبدیل به UNPAID می‌شود
        )
        LiquidityCheck.objects.create(
            customer_name='مشتری ۴', due_date=self.today,
            amount=Decimal('5000000.00'), status='BOUNCED', created_by=self.user
        )

        res = self.client.get('/api/liquidity/checks/summary/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data

        self.assertEqual(data['total_count'], 4)
        self.assertEqual(data['cleared_count'], 1)
        self.assertEqual(data['cleared_amount'], 10000000.0)
        self.assertEqual(data['pending_count'], 1)
        self.assertEqual(data['pending_amount'], 20000000.0)
        self.assertEqual(data['unpaid_count'], 1)
        self.assertEqual(data['unpaid_amount'], 15000000.0)
        self.assertEqual(data['bounced_count'], 1)
        self.assertEqual(data['bounced_amount'], 5000000.0)

    def test_spend_checks_on_expense_flow(self):
        """تست فرآیند خرج چک روی هزینه و کسر صحیح مبلغ نقدی هزینه"""
        expense = LiquidityExpense.objects.create(
            title='خرید پارچه عمده',
            category='SUPPLIER',
            amount=Decimal('200000000.00'),  # ۲۰۰ میلیون تومان
            due_date=self.today + datetime.timedelta(days=20),
            created_by=self.user
        )

        chk1 = LiquidityCheck.objects.create(
            customer_name='خریدار الف',
            due_date=self.today + datetime.timedelta(days=5),
            amount=Decimal('20000000.00'),  # ۲۰ میلیون تومان
            status='PENDING',
            created_by=self.user
        )

        chk2 = LiquidityCheck.objects.create(
            customer_name='خریدار ب',
            due_date=self.today + datetime.timedelta(days=12),
            amount=Decimal('30000000.00'),  # ۳۰ میلیون تومان
            status='PENDING',
            created_by=self.user
        )

        # خرج کردن هر دو چک روی این هزینه
        url = f'/api/liquidity/expenses/{expense.id}/spend-checks/'
        res = self.client.post(url, data={'check_ids': [str(chk1.id), str(chk2.id)]}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        expense.refresh_from_db()
        chk1.refresh_from_db()
        chk2.refresh_from_db()

        # بررسی وضعیت چک‌ها
        self.assertEqual(chk1.status, 'SPENT')
        self.assertEqual(chk1.spent_on_expense, expense)
        self.assertEqual(chk2.status, 'SPENT')
        self.assertEqual(chk2.spent_on_expense, expense)

        # بررسی هزینه: مبلغ اولیه ۲۰۰ میلیون، چک‌های خرج شده ۵۰ میلیون، مبلغ باقیمانده ۱۵۰ میلیون
        self.assertTrue(expense.has_spent_check)
        self.assertEqual(expense.initial_amount, Decimal('200000000.00'))
        self.assertEqual(expense.spent_checks_amount, Decimal('50000000.00'))
        self.assertEqual(expense.amount, Decimal('150000000.00'))

        # تست لغو خرج یکی از چک‌ها
        remove_url = f'/api/liquidity/expenses/{expense.id}/remove-spent-check/'
        res_remove = self.client.post(remove_url, data={'check_id': str(chk1.id)}, format='json')
        self.assertEqual(res_remove.status_code, status.HTTP_200_OK)

        expense.refresh_from_db()
        chk1.refresh_from_db()

        self.assertEqual(chk1.status, 'PENDING')
        self.assertIsNone(chk1.spent_on_expense)
        self.assertIsNone(chk1.spent_at)

        # مبلغ باقیمانده اکنون باید ۱۷۰ میلیون باشد (فقط chk2 با ۳۰ میلیون متصل است)
        self.assertEqual(expense.spent_checks_amount, Decimal('30000000.00'))
        self.assertEqual(expense.amount, Decimal('170000000.00'))
        self.assertTrue(expense.has_spent_check)

    def test_cannot_spend_cleared_or_bounced_check(self):
        """تست عدم امکان خرج کردن چکی که وصول یا برگشت خورده است"""
        expense = LiquidityExpense.objects.create(
            title='اجاره انبار',
            category='RENT',
            amount=Decimal('50000000.00'),
            due_date=self.today + datetime.timedelta(days=15),
            created_by=self.user
        )

        cleared_check = LiquidityCheck.objects.create(
            customer_name='مشتری پاس‌شده',
            due_date=self.today,
            amount=Decimal('10000000.00'),
            status='CLEARED',
            created_by=self.user
        )

        url = f'/api/liquidity/expenses/{expense.id}/spend-checks/'
        res = self.client.post(url, data={'check_ids': [str(cleared_check.id)]}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('قابلیت خرج شدن ندارد', res.data['error'])

    def test_delete_expense_releases_spent_checks(self):
        """تست آزادسازی ایمن چک‌های خرج‌شده هنگام حذف هزینه"""
        expense = LiquidityExpense.objects.create(
            title='هزینه موقت',
            category='OTHER_EXPENSES',
            amount=Decimal('40000000.00'),
            due_date=self.today + datetime.timedelta(days=10),
            created_by=self.user
        )

        chk = LiquidityCheck.objects.create(
            customer_name='مشتری تست حذف',
            due_date=self.today + datetime.timedelta(days=5),
            amount=Decimal('10000000.00'),
            status='PENDING',
            created_by=self.user
        )

        # اختصاص چک به هزینه
        self.client.post(f'/api/liquidity/expenses/{expense.id}/spend-checks/', data={'check_ids': [str(chk.id)]}, format='json')
        chk.refresh_from_db()
        self.assertEqual(chk.status, 'SPENT')

        # حذف هزینه
        res_del = self.client.delete(f'/api/liquidity/expenses/{expense.id}/')
        self.assertIn(res_del.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])

        chk.refresh_from_db()
        self.assertIsNone(chk.spent_on_expense)
        self.assertEqual(chk.status, 'PENDING')
