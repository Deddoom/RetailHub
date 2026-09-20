# -*- coding: utf-8 -*-
from django.test import TestCase
from rest_framework.test import APIClient
from decimal import Decimal
import datetime
from datetime import timedelta

from core.models import (
    CustomUser, Role,
    LiquidityDailyRevenueSetting, LiquidityExpense,
    LiquidityExpensePayment, LiquidityCardTransaction
)


class LiquidityManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='finmanager',
            password='password123',
            first_name='مدیر',
            last_name='مالی'
        )
        self.role_fin, _ = Role.objects.get_or_create(code='FINANCIAL_MANAGER')
        self.user.roles.add(self.role_fin)
        self.client.force_authenticate(user=self.user)

        # تنظیم اولیه درآمد روزانه: ۵۰ میلیون تومان
        self.daily_revenue = LiquidityDailyRevenueSetting.get_current_revenue()
        self.daily_revenue.amount = Decimal('50000000.00')
        self.daily_revenue.updated_by = self.user
        self.daily_revenue.save()

    def test_daily_revenue_api(self):
        # 1. دریافت درآمد روزانه
        res = self.client.get('/api/liquidity/daily-revenue/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(float(res.data['amount']), 50000000.0)

        # 2. تغییر درآمد روزانه
        res = self.client.post('/api/liquidity/daily-revenue/', {'amount': 60000000})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(float(res.data['amount']), 60000000.0)
        self.daily_revenue.refresh_from_db()
        self.assertEqual(self.daily_revenue.amount, Decimal('60000000.00'))

    def test_expense_status_calculations(self):
        today = datetime.date.today()
        # روزانه 50M
        # هزینه 1: حقوق 100M، 10 روز مانده -> بدهی 100M / 10 روز = 10M روزانه -> نسبت 10/50 = 0.20 (< 0.50) -> NORMAL
        exp_normal = LiquidityExpense.objects.create(
            title='حقوق پرسنل',
            category='SALARY',
            amount=Decimal('100000000.00'),
            due_date=today + timedelta(days=10),
            created_by=self.user
        )
        self.assertEqual(exp_normal.calculate_status(), 'NORMAL')

        # هزینه 2: اجاره 120M، 4 روز مانده -> بدهی 120M / 4 روز = 30M روزانه -> نسبت 30/50 = 0.60 (بین 0.50 تا 0.75) -> WARNING
        exp_warning = LiquidityExpense.objects.create(
            title='اجاره شعبه',
            category='RENT',
            amount=Decimal('120000000.00'),
            due_date=today + timedelta(days=4),
            created_by=self.user
        )
        self.assertEqual(exp_warning.calculate_status(), 'WARNING')

        # هزینه 3: خرید فوری 80M، 2 روز مانده -> بدهی 80M / 2 روز = 40M روزانه -> نسبت 40/50 = 0.80 (> 0.75) -> CRITICAL
        exp_critical = LiquidityExpense.objects.create(
            title='خرید بار',
            category='PURCHASE',
            amount=Decimal('80000000.00'),
            due_date=today + timedelta(days=2),
            created_by=self.user
        )
        self.assertEqual(exp_critical.calculate_status(), 'CRITICAL')

        # هزینه 4: عالی (EXCELLENT) -> قبل از موعد سررسید کل مبلغ تخصیص داده شده
        exp_excellent = LiquidityExpense.objects.create(
            title='قبض برق',
            category='BILL',
            amount=Decimal('10000000.00'),
            due_date=today + timedelta(days=5),
            created_by=self.user
        )
        LiquidityExpensePayment.objects.create(
            expense=exp_excellent,
            amount=Decimal('10000000.00'),
            date=today,
            created_by=self.user
        )
        self.assertEqual(exp_excellent.calculate_status(), 'EXCELLENT')

        # هزینه 5: عقب مانده (OVERDUE) -> سررسید گذشته و تسویه نشده
        exp_overdue = LiquidityExpense.objects.create(
            title='چک تامین‌کننده',
            category='CHEQUE',
            amount=Decimal('50000000.00'),
            due_date=today - timedelta(days=3),
            created_by=self.user
        )
        self.assertEqual(exp_overdue.calculate_status(), 'OVERDUE')

        # هزینه 6: تسویه شده (PAID)
        exp_paid = LiquidityExpense.objects.create(
            title='هزینه متفرقه',
            category='MISC',
            amount=Decimal('20000000.00'),
            due_date=today + timedelta(days=1),
            is_paid=True,
            created_by=self.user
        )
        self.assertEqual(exp_paid.calculate_status(), 'PAID')

    def test_expense_crud_and_payment_flow(self):
        today = datetime.date.today()

        # ثبت هزینه جدید
        payload = {
            "name": "حقوق شهریور پرسنل",
            "category": "SALARY",
            "amount": 200000000,
            "due_date": str(today + timedelta(days=15)),
            "description": "حقوق تمام پرسنل"
        }
        res = self.client.post('/api/liquidity/expenses/', payload)
        self.assertEqual(res.status_code, 201)
        expense_id = res.data['id']
        self.assertEqual(res.data['title'], "حقوق شهریور پرسنل")
        self.assertEqual(float(res.data['allocated_amount']), 0.0)
        self.assertEqual(float(res.data['remaining_debt']), 200000000.0)

        # ثبت پرداخت مرحله‌ای اول (50 میلیون)
        res_pay1 = self.client.post(f'/api/liquidity/expenses/{expense_id}/payments/', {
            "amount": 50000000,
            "date": str(today),
            "description": "تخصیص از فروش امروز"
        })
        self.assertEqual(res_pay1.status_code, 201)
        self.assertEqual(float(res_pay1.data['expense']['allocated_amount']), 50000000.0)
        self.assertEqual(float(res_pay1.data['expense']['remaining_debt']), 150000000.0)

        # ثبت پرداخت مرحله‌ای دوم (150 میلیون جهت تکمیل 200 میلیون)
        res_pay2 = self.client.post(f'/api/liquidity/expenses/{expense_id}/payments/', {
            "amount": 150000000,
            "date": str(today),
            "description": "تکمیل وجه حقوق"
        })
        self.assertEqual(res_pay2.status_code, 201)
        self.assertEqual(float(res_pay2.data['expense']['allocated_amount']), 200000000.0)
        self.assertEqual(float(res_pay2.data['expense']['remaining_debt']), 0.0)
        self.assertEqual(res_pay2.data['expense']['status'], 'EXCELLENT')

        # تایید پرداخت نهایی (confirm-payment)
        res_confirm = self.client.post(f'/api/liquidity/expenses/{expense_id}/confirm-payment/')
        self.assertEqual(res_confirm.status_code, 200)
        self.assertTrue(res_confirm.data['expense']['is_paid'])
        self.assertEqual(res_confirm.data['expense']['status'], 'PAID')

    def test_three_cards_behavior(self):
        today = datetime.date.today()

        # ۱. هزینه باز اول: 200 میلیون، 100 میلیون پرداخت شده
        exp1 = LiquidityExpense.objects.create(
            title='حقوق مهر',
            category='SALARY',
            amount=Decimal('200000000.00'),
            due_date=today + timedelta(days=15),
            created_by=self.user
        )
        LiquidityExpensePayment.objects.create(
            expense=exp1,
            amount=Decimal('100000000.00'),
            date=today,
            created_by=self.user
        )

        # هزینه باز دوم: 30 میلیون، 15 میلیون پرداخت شده
        exp2 = LiquidityExpense.objects.create(
            title='اجاره مهر',
            category='RENT',
            amount=Decimal('30000000.00'),
            due_date=today + timedelta(days=20),
            created_by=self.user
        )
        LiquidityExpensePayment.objects.create(
            expense=exp2,
            amount=Decimal('15000000.00'),
            date=today,
            created_by=self.user
        )

        # بررسی کارت هزینه‌ها: باید مجموع 100M + 15M = 115M باشد
        res_cards = self.client.get('/api/liquidity/cards/')
        self.assertEqual(res_cards.status_code, 200)
        self.assertEqual(res_cards.data['expense_card']['total_allocated'], 115000000.0)
        self.assertEqual(res_cards.data['expense_card']['total_target'], 230000000.0)
        self.assertEqual(res_cards.data['expense_card']['remaining_needed'], 115000000.0)
        self.assertEqual(res_cards.data['expense_card']['active_expenses_count'], 2)

        # حالا هزینه اول به طور کامل پرداخت و تایید تسویه می‌شود
        exp1.is_paid = True
        exp1.save()

        # اکنون کارت هزینه‌ها باید فقط شامل هزینه دوم (15M) باشد و 100M از کارت کسر شده باشد!
        res_cards_after = self.client.get('/api/liquidity/cards/')
        self.assertEqual(res_cards_after.data['expense_card']['total_allocated'], 15000000.0)
        self.assertEqual(res_cards_after.data['expense_card']['total_target'], 30000000.0)
        self.assertEqual(res_cards_after.data['expense_card']['remaining_needed'], 15000000.0)
        self.assertEqual(res_cards_after.data['expense_card']['active_expenses_count'], 1)

        # ۲. تست کارت تنخواه
        # واریز 10 میلیون به تنخواه
        res_petty_in = self.client.post('/api/liquidity/cards/petty-cash/transactions/', {
            "transaction_type": "DEPOSIT",
            "amount": 10000000,
            "date": str(today),
            "description": "شارژ تنخواه از فروش دیروز"
        })
        self.assertEqual(res_petty_in.status_code, 201)

        # برداشت 3 میلیون خرج روزمره
        res_petty_out = self.client.post('/api/liquidity/cards/petty-cash/transactions/', {
            "transaction_type": "WITHDRAWAL",
            "amount": 3000000,
            "date": str(today),
            "description": "خرید چای و قند و شوینده"
        })
        self.assertEqual(res_petty_out.status_code, 201)

        # بررسی موجودی تنخواه: 10M - 3M = 7M
        res_petty = self.client.get('/api/liquidity/cards/petty-cash/')
        self.assertEqual(res_petty.data['balance'], 7000000.0)
        self.assertEqual(res_petty.data['total_deposits'], 10000000.0)
        self.assertEqual(res_petty.data['total_withdrawals'], 3000000.0)

        # ۳. تست کارت سود
        # واریز 5 میلیون به سود
        res_profit_in = self.client.post('/api/liquidity/cards/profit/transactions/', {
            "transaction_type": "DEPOSIT",
            "amount": 5000000,
            "date": str(today),
            "description": "سود مازاد دیروز"
        })
        self.assertEqual(res_profit_in.status_code, 201)

        # بررسی موجودی سود
        res_profit = self.client.get('/api/liquidity/cards/profit/')
        self.assertEqual(res_profit.data['balance'], 5000000.0)

    def test_expense_scopes_and_summary(self):
        today = datetime.date.today()

        # هزینه هفته آینده
        LiquidityExpense.objects.create(
            title='هزینه هفته آینده',
            category='BILL',
            amount=Decimal('5000000.00'),
            due_date=today + timedelta(days=3),
            created_by=self.user
        )

        # هزینه گذشته (عقب افتاده)
        LiquidityExpense.objects.create(
            title='هزینه عقب افتاده',
            category='CHEQUE',
            amount=Decimal('10000000.00'),
            due_date=today - timedelta(days=2),
            created_by=self.user
        )

        # هزینه پرداخت شده
        LiquidityExpense.objects.create(
            title='هزینه پرداخت شده',
            category='DAILY',
            amount=Decimal('2000000.00'),
            due_date=today + timedelta(days=1),
            is_paid=True,
            created_by=self.user
        )

        # تست خلاصه شمارنده‌ها
        res_sum = self.client.get('/api/liquidity/expenses/summary/')
        self.assertEqual(res_sum.status_code, 200)
        self.assertEqual(res_sum.data['unpaid_count'], 2)
        self.assertEqual(res_sum.data['paid_count'], 1)
        self.assertEqual(res_sum.data['next_week_count'], 1)
        self.assertEqual(res_sum.data['overdue_count'], 1)

        # تست فیلتر scope=next_week
        res_nw = self.client.get('/api/liquidity/expenses/?scope=next_week')
        self.assertEqual(res_nw.status_code, 200)
        self.assertEqual(len(res_nw.data), 1)
        self.assertEqual(res_nw.data[0]['title'], 'هزینه هفته آینده')

        # تست فیلتر scope=overdue
        res_od = self.client.get('/api/liquidity/expenses/?scope=overdue')
        self.assertEqual(res_od.status_code, 200)
        self.assertEqual(len(res_od.data), 1)
        self.assertEqual(res_od.data[0]['title'], 'هزینه عقب افتاده')

    def test_status_filtering_and_payment_deletion(self):
        today = datetime.date.today()
        # هزینه 1: عادی (10M در 10 روز با درآمد روزانه 50M -> 2%)
        exp1 = LiquidityExpense.objects.create(
            title='هزینه عادی',
            category='SALARY',
            amount=Decimal('10000000.00'),
            due_date=today + timedelta(days=10),
            created_by=self.user
        )

        # هزینه 2: بحرانی (40M در 1 روز با درآمد روزانه 50M -> 80%)
        exp2 = LiquidityExpense.objects.create(
            title='هزینه بحرانی',
            category='PURCHASE',
            amount=Decimal('40000000.00'),
            due_date=today + timedelta(days=1),
            created_by=self.user
        )

        # تست فیلتر وضعیت CRITICAL
        res_crit = self.client.get('/api/liquidity/expenses/?status=CRITICAL')
        self.assertEqual(res_crit.status_code, 200)
        self.assertEqual(len(res_crit.data), 1)
        self.assertEqual(res_crit.data[0]['title'], 'هزینه بحرانی')

        # تست فیلتر وضعیت NORMAL
        res_norm = self.client.get('/api/liquidity/expenses/?status=NORMAL')
        self.assertEqual(res_norm.status_code, 200)
        self.assertEqual(len(res_norm.data), 1)
        self.assertEqual(res_norm.data[0]['title'], 'هزینه عادی')

        # اضافه کردن پرداخت به هزینه 1 و سپس حذف آن
        res_pay = self.client.post(f'/api/liquidity/expenses/{exp1.id}/payments/', {
            "amount": 5000000,
            "date": str(today),
            "description": "تخصیص ۵ میلیون"
        })
        self.assertEqual(res_pay.status_code, 201)
        payment_id = res_pay.data['payment']['id']
        self.assertEqual(float(res_pay.data['expense']['allocated_amount']), 5000000.0)

        # حذف پرداخت
        res_del = self.client.delete(f'/api/liquidity/expenses/{exp1.id}/payments/{payment_id}/')
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(float(res_del.data['expense']['allocated_amount']), 0.0)

        # تایید پرداخت و سپس لغو تایید
        res_conf = self.client.post(f'/api/liquidity/expenses/{exp1.id}/confirm-payment/')
        self.assertEqual(res_conf.status_code, 200)
        self.assertTrue(res_conf.data['expense']['is_paid'])

        res_unconf = self.client.post(f'/api/liquidity/expenses/{exp1.id}/unconfirm-payment/')
        self.assertEqual(res_unconf.status_code, 200)
        self.assertFalse(res_unconf.data['expense']['is_paid'])

    def test_permission_checks(self):
        # کاربر عادی (بدون دسترسی مالی یا ادمین)
        cashier = CustomUser.objects.create_user(username='cashier1', password='p1')
        role_cashier, _ = Role.objects.get_or_create(code='CASHIER')
        cashier.roles.add(role_cashier)

        unauth_client = APIClient()
        unauth_client.force_authenticate(user=cashier)

        # صندوق‌دار نباید اجازه ساخت هزینه نقدینگی داشته باشد (403 Forbidden)
        res = unauth_client.post('/api/liquidity/expenses/', {
            "title": "هزینه غیرمجاز",
            "amount": 1000,
            "due_date": str(datetime.date.today())
        })
        self.assertEqual(res.status_code, 403)

        # صندوق‌دار نباید اجازه ثبت تراکنش تنخواه داشته باشد
        res_tx = unauth_client.post('/api/liquidity/cards/petty-cash/transactions/', {
            "transaction_type": "DEPOSIT",
            "amount": 1000
        })
        self.assertEqual(res_tx.status_code, 403)
