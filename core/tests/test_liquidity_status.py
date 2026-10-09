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
    LiquidityCardTransaction,
    CATEGORY_PERCENTAGES,
)

User = get_user_model()


class LiquidityStatusFormulaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='fin_mgr',
            password='Password123!',
            first_name='مدیر',
            last_name='مالی',
            is_superuser=True
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.revenue_setting = LiquidityDailyRevenueSetting.get_current_revenue()
        self.revenue_setting.amount = Decimal('10000000.00')  # ۱۰ میلیون تومان فروش روزانه
        self.revenue_setting.save()

        self.today = datetime.date.today()

    def test_category_percentages_validity(self):
        """بررسی دقیق مقادیر درصدهای ۹‌گانه و اینکه مجموع آن‌ها دقیقاً ۱۰۰٪ است"""
        total = sum(CATEGORY_PERCENTAGES.values())
        self.assertEqual(total, Decimal('1.00'))

        self.assertEqual(CATEGORY_PERCENTAGES['SUPPLIER'], Decimal('0.51'))
        self.assertEqual(CATEGORY_PERCENTAGES['SALARY'], Decimal('0.14'))
        self.assertEqual(CATEGORY_PERCENTAGES['RENT'], Decimal('0.05'))
        self.assertEqual(CATEGORY_PERCENTAGES['INSTALLMENTS'], Decimal('0.09'))
        self.assertEqual(CATEGORY_PERCENTAGES['OTHER_EXPENSES'], Decimal('0.07'))
        self.assertEqual(CATEGORY_PERCENTAGES['MANAGEMENT'], Decimal('0.03'))
        self.assertEqual(CATEGORY_PERCENTAGES['SAVINGS'], Decimal('0.07'))
        self.assertEqual(CATEGORY_PERCENTAGES['CHARITY'], Decimal('0.02'))
        self.assertEqual(CATEGORY_PERCENTAGES['EQUIPMENT'], Decimal('0.02'))

    def test_status_paid(self):
        """هزینه‌ای که تسویه نهایی شده است باید وضعیت PAID داشته باشد"""
        exp = LiquidityExpense.objects.create(
            title='هزینه پرداخت شده',
            category='SUPPLIER',
            amount=Decimal('50000000.00'),
            due_date=self.today + datetime.timedelta(days=10),
            is_paid=True,
            created_by=self.user
        )
        metrics = exp.calculate_liquidity_metrics()
        self.assertEqual(metrics['status'], 'PAID')
        self.assertEqual(exp.calculate_status(), 'PAID')

    def test_status_overdue(self):
        """هزینه‌ای که سررسیدش گذشته و پرداخت نشده باید وضعیت OVERDUE داشته باشد"""
        exp = LiquidityExpense.objects.create(
            title='هزینه معوقه',
            category='SALARY',
            amount=Decimal('50000000.00'),
            due_date=self.today - datetime.timedelta(days=3),
            is_paid=False,
            created_by=self.user
        )
        metrics = exp.calculate_liquidity_metrics()
        self.assertEqual(metrics['status'], 'OVERDUE')
        self.assertEqual(exp.calculate_status(), 'OVERDUE')

    def test_status_critical_negative_available_cash(self):
        """اگر نقدینگی در دسترس صفر یا منفی باشد، وضعیت قطعاً CRITICAL است"""
        exp = LiquidityExpense.objects.create(
            title='هزینه بحرانی بی‌پول',
            category='RENT',
            amount=Decimal('100000000.00'),
            due_date=self.today,  # امروز سررسید است (ورودی آینده = ۰)
            is_paid=False,
            created_by=self.user
        )
        # موجودی کارت اجاره صفر، ورودی صفر -> available_cash = 0
        metrics = exp.calculate_liquidity_metrics()
        self.assertEqual(metrics['status'], 'CRITICAL')
        self.assertEqual(metrics['available_cash'], Decimal('0.00'))

    def test_status_critical_ratio_ge_1(self):
        """اگر کسر بزرگتر مساوی ۱ باشد، وضعیت CRITICAL است"""
        # شارژ کارت تامین‌کننده با ۴۰ میلیون
        LiquidityCardTransaction.objects.create(
            card_type='SUPPLIER',
            transaction_type='DEPOSIT',
            amount=Decimal('40000000.00'),
            created_by=self.user
        )
        # فروش روزانه صفر در نظر بگیریم تا نقدینگی در دسترس = ۴۰ میلیون باشد
        exp = LiquidityExpense.objects.create(
            title='هزینه ۵۰ میلیونی با نقدینگی ۴۰ میلیون',
            category='SUPPLIER',
            amount=Decimal('50000000.00'),
            due_date=self.today,
            is_paid=False,
            created_by=self.user
        )
        # کسر = 50M / 40M = 1.25 >= 1.0 -> CRITICAL
        metrics = exp.calculate_liquidity_metrics()
        self.assertEqual(metrics['status'], 'CRITICAL')
        self.assertAlmostEqual(float(metrics['ratio']), 1.25, places=2)

    def test_status_warning(self):
        """اگر کسر بین 0.80 تا 1.0 باشد، وضعیت WARNING است"""
        # کارت را با ۶۰ میلیون شارژ می‌کنیم
        LiquidityCardTransaction.objects.create(
            card_type='INSTALLMENTS',
            transaction_type='DEPOSIT',
            amount=Decimal('60000000.00'),
            created_by=self.user
        )
        exp = LiquidityExpense.objects.create(
            title='هزینه قسط ۵۰ میلیونی با موجودی ۶۰ میلیون',
            category='INSTALLMENTS',
            amount=Decimal('50000000.00'),
            due_date=self.today,
            is_paid=False,
            created_by=self.user
        )
        # کسر = 50M / 60M = 0.8333 -> بین 0.8 و 1.0 -> WARNING
        metrics = exp.calculate_liquidity_metrics()
        self.assertEqual(metrics['status'], 'WARNING')
        self.assertAlmostEqual(float(metrics['ratio']), 0.8333, places=2)

    def test_status_normal(self):
        """اگر کسر بین 0.30 تا 0.80 باشد، وضعیت NORMAL است"""
        LiquidityCardTransaction.objects.create(
            card_type='MANAGEMENT',
            transaction_type='DEPOSIT',
            amount=Decimal('100000000.00'),
            created_by=self.user
        )
        exp = LiquidityExpense.objects.create(
            title='هزینه ۵۰ میلیونی با موجودی ۱۰۰ میلیون',
            category='MANAGEMENT',
            amount=Decimal('50000000.00'),
            due_date=self.today,
            is_paid=False,
            created_by=self.user
        )
        # کسر = 50M / 100M = 0.50 -> NORMAL
        metrics = exp.calculate_liquidity_metrics()
        self.assertEqual(metrics['status'], 'NORMAL')
        self.assertAlmostEqual(float(metrics['ratio']), 0.50, places=2)

    def test_status_excellent(self):
        """اگر کسر کمتر از 0.30 باشد، وضعیت EXCELLENT است"""
        LiquidityCardTransaction.objects.create(
            card_type='SAVINGS',
            transaction_type='DEPOSIT',
            amount=Decimal('200000000.00'),
            created_by=self.user
        )
        exp = LiquidityExpense.objects.create(
            title='هزینه ۵۰ میلیونی با موجودی ۲۰۰ میلیون',
            category='SAVINGS',
            amount=Decimal('50000000.00'),
            due_date=self.today,
            is_paid=False,
            created_by=self.user
        )
        # کسر = 50M / 200M = 0.25 < 0.30 -> EXCELLENT
        metrics = exp.calculate_liquidity_metrics()
        self.assertEqual(metrics['status'], 'EXCELLENT')
        self.assertAlmostEqual(float(metrics['ratio']), 0.25, places=2)

    def test_upstream_expenses_and_incoming_sales(self):
        """
        آزمون جامع اثر فروش روزانه، درصدهای تخصیص و کسر هزینه‌های بالادستی:
        - کارت تامین‌کننده: دارای ۴۰ میلیون موجودی
        - فروش روزانه: ۱۰ میلیون تومان (۵۱٪ یعنی روزانه ۵٫۱ میلیون سهم کارت تامین‌کننده)
        - هزینه ۱ (سررسید ۵ روز دیگر): مبلغ ۳۰ میلیون
          ورودی = ۵ × ۵٫۱ = ۲۵٫۵ میلیون
          نقدینگی در دسترس = ۴۰ + ۲۵٫۵ - ۰ = ۶۵٫۵ میلیون
          کسر = ۳۰ / ۶۵٫۵ = ۰٫۴۵۸ -> NORMAL
        - هزینه ۲ (سررسید ۱۰ روز دیگر): مبلغ ۵۰ میلیون
          ورودی = ۱۰ × ۵٫۱ = ۵۱ میلیون
          هزینه بالادستی = ۳۰ میلیون (هزینه ۱)
          نقدینگی در دسترس = ۴۰ + ۵۱ - ۳۰ = ۶۱ میلیون
          کسر = ۵۰ / ۶۱ = ۰٫۸۱۹۷ -> WARNING
        """
        LiquidityCardTransaction.objects.create(
            card_type='SUPPLIER',
            transaction_type='DEPOSIT',
            amount=Decimal('40000000.00'),
            created_by=self.user
        )

        exp1 = LiquidityExpense.objects.create(
            title='هزینه ۱ تامین‌کننده (۵ روز دیگر)',
            category='SUPPLIER',
            amount=Decimal('30000000.00'),
            due_date=self.today + datetime.timedelta(days=5),
            is_paid=False,
            created_by=self.user
        )

        exp2 = LiquidityExpense.objects.create(
            title='هزینه ۲ تامین‌کننده (۱۰ روز دیگر)',
            category='SUPPLIER',
            amount=Decimal('50000000.00'),
            due_date=self.today + datetime.timedelta(days=10),
            is_paid=False,
            created_by=self.user
        )

        # محاسبه دسته‌ای و بررسی تطابق
        batch = LiquidityExpense.batch_calculate_metrics([exp1, exp2])

        m1 = batch[exp1.id]
        self.assertEqual(m1['upstream_expenses'], Decimal('0.00'))
        self.assertEqual(m1['expected_incoming'], Decimal('25500000.00'))  # 10M * 0.51 * 5
        self.assertEqual(m1['available_cash'], Decimal('65500000.00'))     # 40M + 25.5M
        self.assertAlmostEqual(float(m1['ratio']), 30000000 / 65500000, places=4)
        self.assertEqual(m1['status'], 'NORMAL')

        m2 = batch[exp2.id]
        self.assertEqual(m2['upstream_expenses'], Decimal('30000000.00'))  # کسر هزینه ۱
        self.assertEqual(m2['expected_incoming'], Decimal('51000000.00'))  # 10M * 0.51 * 10
        self.assertEqual(m2['available_cash'], Decimal('61000000.00'))     # 40M + 51M - 30M
        self.assertAlmostEqual(float(m2['ratio']), 50000000 / 61000000, places=4)
        self.assertEqual(m2['status'], 'WARNING')

    def test_summary_api_endpoint(self):
        """آزمون اندپوینت summary و درستی شمارش وضعیت‌های جدید"""
        # ایجاد ۳ هزینه با وضعیت‌های مختلف
        LiquidityExpense.objects.create(
            title='هزینه ۱ پرداخت شده',
            category='RENT',
            amount=Decimal('10000000.00'),
            due_date=self.today,
            is_paid=True,
            created_by=self.user
        )
        LiquidityExpense.objects.create(
            title='هزینه ۲ عقب‌افتاده',
            category='RENT',
            amount=Decimal('10000000.00'),
            due_date=self.today - datetime.timedelta(days=2),
            is_paid=False,
            created_by=self.user
        )
        LiquidityExpense.objects.create(
            title='هزینه ۳ بحرانی',
            category='RENT',
            amount=Decimal('100000000.00'),
            due_date=self.today,
            is_paid=False,
            created_by=self.user
        )

        res = self.client.get('/api/liquidity/expenses/summary/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertEqual(data['total_count'], 3)
        self.assertEqual(data['paid_count'], 1)
        self.assertEqual(data['overdue_count'], 1)
        self.assertEqual(data['critical_count'], 1)

    def test_list_api_endpoint_with_status_filter_and_fields(self):
        """آزمون فیلتر وضعیت در لیست هزینه‌ها و بررسی فیلدهای جدید در خروجی سریالایزر"""
        exp = LiquidityExpense.objects.create(
            title='هزینه تامین کننده فعال',
            category='SUPPLIER',
            amount=Decimal('50000000.00'),
            due_date=self.today + datetime.timedelta(days=10),
            is_paid=False,
            created_by=self.user
        )

        res = self.client.get('/api/liquidity/expenses/?scope=unpaid')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.json()
        self.assertTrue(len(results) >= 1)

        item = next(x for x in results if x['id'] == str(exp.id))
        self.assertIn('status', item)
        self.assertIn('ratio', item)
        self.assertIn('category_percentage', item)
        self.assertEqual(item['category_percentage'], 0.51)
        self.assertIn('card_balance', item)
        self.assertIn('upstream_expenses', item)
        self.assertIn('expected_incoming', item)
        self.assertIn('available_cash', item)
