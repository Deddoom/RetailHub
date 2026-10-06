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
        # هزینه 1: حقوق 100M، 10 روز مانده -> NORMAL
        exp_normal = LiquidityExpense.objects.create(
            title='حقوق پرسنل',
            category='SALARY',
            amount=Decimal('100000000.00'),
            due_date=today + timedelta(days=10),
            created_by=self.user
        )
        self.assertEqual(exp_normal.calculate_status(), 'NORMAL')

        # هزینه 2: اجاره 120M، 4 روز مانده -> WARNING
        exp_warning = LiquidityExpense.objects.create(
            title='اجاره شعبه',
            category='RENT',
            amount=Decimal('120000000.00'),
            due_date=today + timedelta(days=4),
            created_by=self.user
        )
        self.assertEqual(exp_warning.calculate_status(), 'WARNING')

        # هزینه 3: خرید فوری 80M، 2 روز مانده -> CRITICAL
        exp_critical = LiquidityExpense.objects.create(
            title='خرید بار تامین کننده',
            category='SUPPLIER',
            amount=Decimal('80000000.00'),
            due_date=today + timedelta(days=2),
            created_by=self.user
        )
        self.assertEqual(exp_critical.calculate_status(), 'CRITICAL')

        # هزینه 4: عالی (EXCELLENT)
        exp_excellent = LiquidityExpense.objects.create(
            title='قبض برق و سایر',
            category='OTHER_EXPENSES',
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

        # هزینه 5: عقب مانده (OVERDUE)
        exp_overdue = LiquidityExpense.objects.create(
            title='قسط تامین‌کننده',
            category='SUPPLIER',
            amount=Decimal('50000000.00'),
            due_date=today - timedelta(days=3),
            created_by=self.user
        )
        self.assertEqual(exp_overdue.calculate_status(), 'OVERDUE')

        # هزینه 6: تسویه شده (PAID)
        exp_paid = LiquidityExpense.objects.create(
            title='هزینه پرداخت شده',
            category='OTHER_EXPENSES',
            amount=Decimal('20000000.00'),
            due_date=today + timedelta(days=1),
            is_paid=True,
            created_by=self.user
        )
        self.assertEqual(exp_paid.calculate_status(), 'PAID')

    def test_expense_crud_and_strict_payment_flow(self):
        today = datetime.date.today()

        # ثبت هزینه جدید حقوق 200M
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
        self.assertEqual(float(res.data['remaining_debt']), 200000000.0)

        # تلاش برای تایید پرداخت قبل از شارژ کارت حقوق -> باید با 400 مواجه شود (قفل سخت‌گیرانه)
        res_fail_confirm = self.client.post(f'/api/liquidity/expenses/{expense_id}/confirm-payment/')
        self.assertEqual(res_fail_confirm.status_code, 400)
        self.assertIn("کافی نیست", res_fail_confirm.data['error'])

        # شارژ کارت حقوق به مبلغ 250 میلیون
        res_charge = self.client.post('/api/liquidity/cards/salary/transactions/', {
            "transaction_type": "DEPOSIT",
            "amount": 250000000,
            "date": str(today),
            "description": "شارژ حقوق"
        })
        self.assertEqual(res_charge.status_code, 201)

        # تایید پرداخت نهایی (اکنون موجودی 250M >= 200M است)
        res_confirm = self.client.post(f'/api/liquidity/expenses/{expense_id}/confirm-payment/')
        self.assertEqual(res_confirm.status_code, 200)
        self.assertTrue(res_confirm.data['expense']['is_paid'])
        self.assertEqual(res_confirm.data['expense']['status'], 'PAID')

        # بررسی موجودی کارت حقوق: 250M - 200M = 50M
        res_sal_card = self.client.get('/api/liquidity/cards/salary/')
        self.assertEqual(res_sal_card.status_code, 200)
        self.assertEqual(res_sal_card.data['balance'], 50000000.0)
        self.assertEqual(res_sal_card.data['total_withdrawals'], 200000000.0)

    def test_nine_cards_behavior(self):
        today = datetime.date.today()

        # 1. بررسی لیست تمام ۹ کارت در overview
        res_overview = self.client.get('/api/liquidity/cards/')
        self.assertEqual(res_overview.status_code, 200)
        self.assertEqual(len(res_overview.data['cards']), 9)
        self.assertIn('salary', res_overview.data['cards_by_type'])
        self.assertIn('rent', res_overview.data['cards_by_type'])
        self.assertIn('supplier', res_overview.data['cards_by_type'])

        # 2. واریز 200 میلیون به کارت اجاره
        res_rent_dep = self.client.post('/api/liquidity/cards/rent/transactions/', {
            "transaction_type": "DEPOSIT",
            "amount": 200000000,
            "date": str(today),
            "description": "شارژ کارت اجاره"
        })
        self.assertEqual(res_rent_dep.status_code, 201)

        # 3. ثبت چند هزینه در دسته اجاره:
        # هزینه الف: 20 میلیون، سررسید 10 روز آینده (داخل بازه ۳۰ روز)
        exp_a = LiquidityExpense.objects.create(
            title='اجاره انبار',
            category='RENT',
            amount=Decimal('20000000.00'),
            due_date=today + timedelta(days=10),
            created_by=self.user
        )
        # هزینه ب: 30 میلیون، سررسید 25 روز آینده (داخل بازه ۳۰ روز)
        exp_b = LiquidityExpense.objects.create(
            title='اجاره فروشگاه مرکزی',
            category='RENT',
            amount=Decimal('30000000.00'),
            due_date=today + timedelta(days=25),
            created_by=self.user
        )
        # هزینه ج: 10 میلیون، معوقه (سررسید 4 روز پیش، هنوز پرداخت نشده -> باید در مجموع هزینه باشد)
        exp_c = LiquidityExpense.objects.create(
            title='معوقه اجاره دفتر',
            category='RENT',
            amount=Decimal('10000000.00'),
            due_date=today - timedelta(days=4),
            created_by=self.user
        )
        # هزینه د: 50 میلیون، سررسید 45 روز آینده (> ۳۰ روز -> نباید در مجموع هزینه باشد)
        exp_d = LiquidityExpense.objects.create(
            title='اجاره ماه دوم بعد',
            category='RENT',
            amount=Decimal('50000000.00'),
            due_date=today + timedelta(days=45),
            created_by=self.user
        )

        # بررسی کارت اجاره:
        # مجموع هزینه‌های ۳۰ روز آینده: 20M + 30M + 10M = 60M (هزینه 50M خارج از بازه است)
        res_rent = self.client.get('/api/liquidity/cards/rent/')
        self.assertEqual(res_rent.status_code, 200)
        self.assertEqual(res_rent.data['balance'], 200000000.0)
        self.assertEqual(res_rent.data['total_expenses'], 60000000.0)
        self.assertEqual(res_rent.data['expenses_count'], 3)

        # 4. حالا هزینه «اجاره فروشگاه مرکزی» (30 میلیون) تایید پرداخت می‌شود
        res_pay_b = self.client.post(f'/api/liquidity/expenses/{exp_b.id}/confirm-payment/')
        self.assertEqual(res_pay_b.status_code, 200)

        # موجودی کارت اجاره باید 200M - 30M = 170M شود!
        # مجموع هزینه‌ها باید 60M - 30M = 30M شود!
        res_rent_after = self.client.get('/api/liquidity/cards/rent/')
        self.assertEqual(res_rent_after.data['balance'], 170000000.0)
        self.assertEqual(res_rent_after.data['total_expenses'], 30000000.0)
        self.assertEqual(res_rent_after.data['expenses_count'], 2)

        # 5. تست لغو تایید پرداخت (unconfirm-payment):
        # باید تراکنش کسر باطل شده، موجودی به 200M برگردد و مجموع هزینه به 60M برگردد!
        res_unconf = self.client.post(f'/api/liquidity/expenses/{exp_b.id}/unconfirm-payment/')
        self.assertEqual(res_unconf.status_code, 200)

        res_rent_restored = self.client.get('/api/liquidity/cards/rent/')
        self.assertEqual(res_rent_restored.data['balance'], 200000000.0)
        self.assertEqual(res_rent_restored.data['total_expenses'], 60000000.0)

    def test_expense_scopes_and_summary(self):
        today = datetime.date.today()

        # هزینه هفته آینده
        LiquidityExpense.objects.create(
            title='هزینه هفته آینده',
            category='OTHER_EXPENSES',
            amount=Decimal('5000000.00'),
            due_date=today + timedelta(days=3),
            created_by=self.user
        )

        # هزینه گذشته (عقب افتاده)
        LiquidityExpense.objects.create(
            title='هزینه عقب افتاده',
            category='SUPPLIER',
            amount=Decimal('10000000.00'),
            due_date=today - timedelta(days=2),
            created_by=self.user
        )

        # هزینه پرداخت شده
        LiquidityExpense.objects.create(
            title='هزینه پرداخت شده',
            category='OTHER_EXPENSES',
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
        # هزینه 1: عادی
        exp1 = LiquidityExpense.objects.create(
            title='هزینه عادی',
            category='SALARY',
            amount=Decimal('10000000.00'),
            due_date=today + timedelta(days=10),
            created_by=self.user
        )

        # هزینه 2: بحرانی
        exp2 = LiquidityExpense.objects.create(
            title='هزینه بحرانی',
            category='SUPPLIER',
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

        # اضافه کردن پرداخت مرحله‌ای به هزینه 1 و سپس حذف آن
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

    def test_permission_checks(self):
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

        # صندوق‌دار نباید اجازه ثبت تراکنش کارت داشته باشد
        res_tx = unauth_client.post('/api/liquidity/cards/salary/transactions/', {
            "transaction_type": "DEPOSIT",
            "amount": 1000
        })
        self.assertEqual(res_tx.status_code, 403)

    def test_card_edge_cases_and_error_handling(self):
        today = datetime.date.today()

        # 1. تست آدرس با فرمت kebab-case: other-expenses
        res_other = self.client.get('/api/liquidity/cards/other-expenses/')
        self.assertEqual(res_other.status_code, 200)
        self.assertEqual(res_other.data['card_type'], 'OTHER_EXPENSES')
        self.assertEqual(res_other.data['title'], 'کارت سایر هزینه ها')

        # 2. تست کارت نامعتبر (404)
        res_invalid = self.client.get('/api/liquidity/cards/invalid-card/')
        self.assertEqual(res_invalid.status_code, 404)
        self.assertIn("کارت نامعتبر است", res_invalid.data['error'])

        # 3. ثبت تراکنش از اندپوینت عمومی با فیلد card_type
        res_gen = self.client.post('/api/liquidity/cards/transactions/', {
            "card_type": "EQUIPMENT",
            "transaction_type": "DEPOSIT",
            "amount": 80000000,
            "date": str(today),
            "description": "خرید دستگاه بارکدخوان و شارژ کارت"
        })
        self.assertEqual(res_gen.status_code, 201)
        tx_id = res_gen.data['transaction']['id']

        # بررسی موجودی تجهیزات
        res_eq = self.client.get('/api/liquidity/cards/equipment/')
        self.assertEqual(res_eq.data['balance'], 80000000.0)

        # 4. حذف تراکنش
        res_del = self.client.delete(f'/api/liquidity/cards/transactions/{tx_id}/')
        self.assertEqual(res_del.status_code, 200)

        # بررسی برگشت موجودی تجهیزات به صفر
        res_eq_zero = self.client.get('/api/liquidity/cards/equipment/')
        self.assertEqual(res_eq_zero.data['balance'], 0.0)

        # 5. خطا در تایید مجدد هزینه پرداخت شده
        exp = LiquidityExpense.objects.create(
            title='هزینه تست',
            category='CHARITY',
            amount=Decimal('1000000.00'),
            due_date=today,
            created_by=self.user
        )
        # شارژ کارت خیریه
        self.client.post('/api/liquidity/cards/charity/transactions/', {
            "transaction_type": "DEPOSIT",
            "amount": 2000000
        })
        # پرداخت اول: موفق
        res_p1 = self.client.post(f'/api/liquidity/expenses/{exp.id}/confirm-payment/')
        self.assertEqual(res_p1.status_code, 200)

        # پرداخت دوم: خطای 400 چون قبلاً پرداخت شده
        res_p2 = self.client.post(f'/api/liquidity/expenses/{exp.id}/confirm-payment/')
        self.assertEqual(res_p2.status_code, 400)
        self.assertIn("قبلاً", res_p2.data['error'])

        # 6. لغو پرداخت روی هزینه پرداخت‌نشده: خطای 400
        unpaid_exp = LiquidityExpense.objects.create(
            title='هزینه باز',
            category='SAVINGS',
            amount=Decimal('500000.00'),
            due_date=today,
            created_by=self.user
        )
        res_unconf_fail = self.client.post(f'/api/liquidity/expenses/{unpaid_exp.id}/unconfirm-payment/')
        self.assertEqual(res_unconf_fail.status_code, 400)
