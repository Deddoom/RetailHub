# -*- coding: utf-8 -*-
from decimal import Decimal
import datetime
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from core.models import (
    CustomUser, Role, LiquidityExpense, LiquidityCardTransaction
)


class LiquidityAllTransactionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.role_admin, _ = Role.objects.get_or_create(code='ADMIN')
        self.role_fin, _ = Role.objects.get_or_create(code='FINANCIAL_MANAGER')

        self.user = CustomUser.objects.create_user(username='admin_fin', is_superuser=True)
        self.user.roles.add(self.role_admin, self.role_fin)
        self.client.force_authenticate(user=self.user)

        # ایجاد هزینه جهت اتصال به تراکنش برداشت
        self.expense = LiquidityExpense.objects.create(
            title="قبض برق شعبه مدرس",
            category="OTHER_EXPENSES",
            amount=Decimal('4500000.00'),
            due_date=datetime.date.today(),
            created_by=self.user,
            is_paid=True
        )

        # تراکنش ۱: واریز به کارت حقوق
        self.tx1 = LiquidityCardTransaction.objects.create(
            card_type='SALARY',
            transaction_type='DEPOSIT',
            amount=Decimal('50000000.00'),
            date=datetime.date(2026, 10, 20),
            description="واریز شارژ کارت حقوق",
            created_by=self.user
        )

        # تراکنش ۲: برداشت عادی از کارت اجاره
        self.tx2 = LiquidityCardTransaction.objects.create(
            card_type='RENT',
            transaction_type='WITHDRAWAL',
            amount=Decimal('15000000.00'),
            date=datetime.date(2026, 10, 21),
            description="برداشت بابت ودیعه",
            created_by=self.user
        )

        # تراکنش ۳: برداشت ناشی از تسویه هزینه
        self.tx3 = LiquidityCardTransaction.objects.create(
            card_type='OTHER_EXPENSES',
            transaction_type='WITHDRAWAL',
            amount=Decimal('4500000.00'),
            date=datetime.date(2026, 10, 22),
            description="تسویه و پرداخت هزینه: قبض برق شعبه مدرس",
            expense=self.expense,
            created_by=self.user
        )

    def test_all_transactions_pagination_and_fields(self):
        """تست ساختار خروجی، فیلدهای مورد نیاز و صفحه‌بندی پیش‌فرض ۲۰تایی"""
        res = self.client.get('/api/liquidity/cards/transactions/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # بررسی وجود ساختار صفحه‌بندی
        self.assertIn('count', res.data)
        self.assertIn('total_pages', res.data)
        self.assertIn('results', res.data)
        self.assertEqual(res.data['count'], 3)

        results = res.data['results']
        # باید به ترتیب تاریخ نزولی مرتب شده باشد (tx3 جدیدتر است)
        self.assertEqual(results[0]['id'], str(self.tx3.id))
        self.assertEqual(results[0]['transaction_type_code'], 'EXPENSE_PAYMENT')
        self.assertEqual(results[0]['transaction_type_display'], 'پرداخت هزینه')
        self.assertEqual(results[0]['expense_title'], 'قبض برق شعبه مدرس')
        self.assertEqual(results[0]['expense_id'], str(self.expense.id))
        self.assertEqual(results[0]['card_title'], 'کارت سایر هزینه ها')
        self.assertEqual(results[0]['amount'], '4500000.00')

        # بررسی تراکنش واریز
        deposit_tx = next(r for r in results if r['id'] == str(self.tx1.id))
        self.assertEqual(deposit_tx['transaction_type_code'], 'DEPOSIT')
        self.assertEqual(deposit_tx['transaction_type_display'], 'واریز به کارت')
        self.assertIsNone(deposit_tx['expense_title'])
        self.assertEqual(deposit_tx['card_title'], 'کارت حقوق')

        # بررسی تراکنش برداشت عادی
        withd_tx = next(r for r in results if r['id'] == str(self.tx2.id))
        self.assertEqual(withd_tx['transaction_type_code'], 'WITHDRAWAL')
        self.assertEqual(withd_tx['transaction_type_display'], 'برداشت از کارت')
        self.assertIsNone(withd_tx['expense_title'])
        self.assertEqual(withd_tx['card_title'], 'کارت اجاره')

    def test_all_transactions_filters(self):
        """تست فیلترهای نوع، کارت و جستجو"""
        # فیلتر نوع: فقط واریز
        res_dep = self.client.get('/api/liquidity/cards/transactions/?type=deposit')
        self.assertEqual(res_dep.data['count'], 1)
        self.assertEqual(res_dep.data['results'][0]['id'], str(self.tx1.id))

        # فیلتر نوع: فقط پرداخت هزینه
        res_exp = self.client.get('/api/liquidity/cards/transactions/?type=expense')
        self.assertEqual(res_exp.data['count'], 1)
        self.assertEqual(res_exp.data['results'][0]['id'], str(self.tx3.id))

        # فیلتر کارت: فقط کارت اجاره
        res_rent = self.client.get('/api/liquidity/cards/transactions/?card_type=rent')
        self.assertEqual(res_rent.data['count'], 1)
        self.assertEqual(res_rent.data['results'][0]['id'], str(self.tx2.id))

        # دسترسی از طریق Endpoint معادل all-transactions
        res_all_url = self.client.get('/api/liquidity/cards/all-transactions/')
        self.assertEqual(res_all_url.status_code, status.HTTP_200_OK)
        self.assertEqual(res_all_url.data['count'], 3)
