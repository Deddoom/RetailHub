# -*- coding: utf-8 -*-
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from core.models import CustomUser, Role, Claim, ClaimItem


class ClaimStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.role_admin, _ = Role.objects.get_or_create(code='ADMIN')

        self.user = CustomUser.objects.create_user(username='claim_admin', is_superuser=True)
        self.user.roles.add(self.role_admin)
        self.client.force_authenticate(user=self.user)

    def test_claim_will_not_pay_status(self):
        """ثبت و بازخوانی مطالبه با وضعیت 'پرداخت نمی‌کند'"""
        payload = {
            "customer_name": "بهرام رادان",
            "customer_phone": "09121112233",
            "total_debt_amount": "3000000.00",
            "status": "WILL_NOT_PAY",
            "taken_date": "2026-10-10",
            "payment_deadline": "2026-10-20",
            "seller": "علی فروشنده",
            "description": "مشتری اعلام کرد پرداخت نمی‌کند",
            "items": [
                {"item_name": "کود تقویتی", "quantity": 3, "unit_price": "1000000.00"}
            ]
        }

        res = self.client.post('/api/claims/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], 'WILL_NOT_PAY')
        self.assertEqual(res.data['status_display'], 'پرداخت نمی‌کند')

        claim_id = res.data['id']
        claim = Claim.objects.get(id=claim_id)
        self.assertEqual(claim.status, 'WILL_NOT_PAY')
        self.assertEqual(claim.get_status_display(), 'پرداخت نمی‌کند')

        # به‌روزرسانی وضعیت به REFUSED هم عنوان متناظر را می‌دهد
        patch_res = self.client.patch(f'/api/claims/{claim_id}/', {"status": "REFUSED"}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertIn("پرداخت نمی‌کند", patch_res.data['status_display'])

    def test_claim_pagination(self):
        """تست صفحه‌بندی هوشمند مطالبات (دریافت تکه‌ای)"""
        # ایجاد ۵ مطالبه نمونه
        for i in range(5):
            c = Claim.objects.create(
                customer_name=f"مشتری {i+1}",
                customer_phone=f"0912000000{i}",
                total_debt_amount=Decimal('100000.00'),
                status='UNPAID',
                taken_date='2026-10-01',
                payment_deadline='2026-10-15',
                seller='فروشنده مرکزی',
                created_by=self.user
            )
            ClaimItem.objects.create(claim=c, item_name=f"کالا {i+1}", quantity=1, unit_price=Decimal('100000.00'))

        # بدون پارامتر page -> خروجی لیست معمولی است (جهت سازگاری کلاینت‌های قدیمی)
        res_raw = self.client.get('/api/claims/')
        self.assertEqual(res_raw.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res_raw.data, list)
        self.assertEqual(len(res_raw.data), 5)

        # با پارامتر page و page_size -> خروجی ساختار استاندارد صفحه‌بندی دارد
        res_paged = self.client.get('/api/claims/?page=1&page_size=2')
        self.assertEqual(res_paged.status_code, status.HTTP_200_OK)
        self.assertIn('count', res_paged.data)
        self.assertIn('total_pages', res_paged.data)
        self.assertIn('results', res_paged.data)
        self.assertEqual(res_paged.data['count'], 5)
        self.assertEqual(res_paged.data['total_pages'], 3)
        self.assertEqual(res_paged.data['current_page'], 1)
        self.assertEqual(len(res_paged.data['results']), 2)

    def test_multi_status_filtering(self):
        """تست فیلتر استاتوس‌های مختلف به صورت تکی و چندگانه"""
        Claim.objects.create(
            customer_name="مشتری الف", customer_phone="09121111111",
            total_debt_amount=Decimal('500000.00'), status='UNPAID',
            taken_date='2026-10-01', payment_deadline='2026-10-15', seller='فروشنده ۱', created_by=self.user
        )
        Claim.objects.create(
            customer_name="مشتری ب", customer_phone="09122222222",
            total_debt_amount=Decimal('600000.00'), status='PAID',
            taken_date='2026-10-01', payment_deadline='2026-10-15', seller='فروشنده ۱', created_by=self.user
        )
        Claim.objects.create(
            customer_name="مشتری ج", customer_phone="09123333333",
            total_debt_amount=Decimal('700000.00'), status='WILL_NOT_PAY',
            taken_date='2026-10-01', payment_deadline='2026-10-15', seller='فروشنده ۲', created_by=self.user
        )

        # ۱. فیلتر تک وضعیتی
        res_unpaid = self.client.get('/api/claims/?status=UNPAID')
        self.assertEqual(len(res_unpaid.data), 1)
        self.assertEqual(res_unpaid.data[0]['status'], 'UNPAID')

        # ۲. فیلتر چند وضعیتی جداشده با کاما
        res_multi = self.client.get('/api/claims/?status=UNPAID,WILL_NOT_PAY')
        self.assertEqual(len(res_multi.data), 2)
        statuses = {r['status'] for r in res_multi.data}
        self.assertEqual(statuses, {'UNPAID', 'WILL_NOT_PAY'})

    def test_claim_search(self):
        """تست جستجو در نام مشتری، شماره تلفن، فروشنده و اقلام بدهی"""
        c1 = Claim.objects.create(
            customer_name="احسان علیخانی", customer_phone="09351234567",
            total_debt_amount=Decimal('1200000.00'), status='UNPAID',
            taken_date='2026-10-01', payment_deadline='2026-10-15', seller='رضا فروشنده',
            description="خرید اقساطی گلدان", created_by=self.user
        )
        ClaimItem.objects.create(claim=c1, item_name="گلدان سفالی نقره‌ای", quantity=2, unit_price=Decimal('600000.00'))

        c2 = Claim.objects.create(
            customer_name="مهران مدیری", customer_phone="09129876543",
            total_debt_amount=Decimal('800000.00'), status='UNPAID',
            taken_date='2026-10-01', payment_deadline='2026-10-15', seller='سارا فروشنده',
            description="خرید بوته گل رز", created_by=self.user
        )
        ClaimItem.objects.create(claim=c2, item_name="بوته گل هلندی", quantity=4, unit_price=Decimal('200000.00'))

        # جستجو بر اساس نام مشتری
        res_name = self.client.get('/api/claims/?search=احسان')
        self.assertEqual(len(res_name.data), 1)
        self.assertEqual(res_name.data[0]['id'], str(c1.id))

        # جستجو بر اساس نام کالا
        res_item = self.client.get('/api/claims/?search=هلندی')
        self.assertEqual(len(res_item.data), 1)
        self.assertEqual(res_item.data[0]['id'], str(c2.id))

        # جستجو بر اساس شماره تلفن
        res_phone = self.client.get('/api/claims/?search=0935')
        self.assertEqual(len(res_phone.data), 1)
        self.assertEqual(res_phone.data[0]['id'], str(c1.id))

    def test_status_summary_endpoint(self):
        """تست اندپوینت آمار تفکیکی وضعیت مطالبات جهت تب‌های فرانت‌اند"""
        Claim.objects.create(
            customer_name="تست ۱", customer_phone="09121111111",
            total_debt_amount=Decimal('1000000.00'), status='UNPAID',
            taken_date='2026-10-01', payment_deadline='2026-10-15', seller='فروشنده', created_by=self.user
        )
        Claim.objects.create(
            customer_name="تست ۲", customer_phone="09122222222",
            total_debt_amount=Decimal('2000000.00'), status='UNPAID',
            taken_date='2026-10-01', payment_deadline='2026-10-15', seller='فروشنده', created_by=self.user
        )
        Claim.objects.create(
            customer_name="تست ۳", customer_phone="09123333333",
            total_debt_amount=Decimal('1500000.00'), status='PAID',
            taken_date='2026-10-01', payment_deadline='2026-10-15', seller='فروشنده', created_by=self.user
        )

        res = self.client.get('/api/claims/status-summary/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['total_count'], 3)
        self.assertEqual(res.data['total_amount'], '4500000.00')

        by_status = res.data['by_status']
        self.assertEqual(by_status['UNPAID']['count'], 2)
        self.assertEqual(by_status['UNPAID']['total_amount'], '3000000.00')
        self.assertEqual(by_status['PAID']['count'], 1)
        self.assertEqual(by_status['PAID']['total_amount'], '1500000.00')
        self.assertEqual(by_status['WILL_NOT_PAY']['count'], 0)
