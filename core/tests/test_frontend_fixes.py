# -*- coding: utf-8 -*-
from django.test import TestCase
from decimal import Decimal
import datetime
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from core.models import (
    Role,
    SellerCommissionConfig,
    BranchTransfer,
    LiquidityDailyCharge,
)

User = get_user_model()


class FrontendFixesIntegrationTests(TestCase):
    def setUp(self):
        # Roles
        self.admin_role, _ = Role.objects.get_or_create(code='ADMIN', defaults={'title': 'مدیر سیستم'})
        self.warehouse_role, _ = Role.objects.get_or_create(code='WAREHOUSE', defaults={'title': 'انباردار'})
        self.seller_role, _ = Role.objects.get_or_create(code='SELLER_STAFF', defaults={'title': 'فروشنده'})
        self.cashier_role, _ = Role.objects.get_or_create(code='CASHIER', defaults={'title': 'صندوق‌دار'})
        self.supervisor_role, _ = Role.objects.get_or_create(code='SUPERVISOR', defaults={'title': 'سرپرست'})

        # Admin user
        self.admin = User.objects.create_user(
            username='main_admin',
            password='Password123!',
            first_name='مدیر',
            last_name='کل'
        )
        self.admin.roles.add(self.admin_role)

        # Sellers
        self.seller1 = User.objects.create_user(
            username='seller_one',
            password='Password123!',
            first_name='فروشنده',
            last_name='یک'
        )
        self.seller1.roles.add(self.seller_role)

        self.seller2 = User.objects.create_user(
            username='seller_two',
            password='Password123!',
            first_name='فروشنده',
            last_name='دو'
        )
        self.seller2.roles.add(self.seller_role)

        # Commission configs
        self.config1 = SellerCommissionConfig.objects.create(
            seller=self.seller1,
            model_type='THRESHOLD_SURPLUS',
            threshold_amount=Decimal('100000000'),
            surplus_percentage=Decimal('2.5'),
            reward_active=True,
            reward_milestones=[{'target_amount': 200000000, 'reward_amount': 2000000}],
            created_by=self.admin
        )

        self.config2 = SellerCommissionConfig.objects.create(
            seller=self.seller2,
            model_type='THRESHOLD_SURPLUS',
            threshold_amount=Decimal('150000000'),
            surplus_percentage=Decimal('3.0'),
            reward_active=False,
            reward_milestones=[],
            created_by=self.admin
        )

        # Cashier and Supervisors for transfer
        self.cashier = User.objects.create_user(username='cashier_user', password='Password123!')
        self.cashier.roles.add(self.cashier_role)
        self.sup1 = User.objects.create_user(username='sup_source', password='Password123!')
        self.sup1.roles.add(self.supervisor_role)
        self.sup2 = User.objects.create_user(username='sup_dest', password='Password123!')
        self.sup2.roles.add(self.supervisor_role)

        # Warehouse user
        self.warehouse_user = User.objects.create_user(username='warehouse_man', password='Password123!')
        self.warehouse_user.roles.add(self.warehouse_role)

        # Restricted Liquidity users: chahkandi and ali
        self.chahkandi_user = User.objects.create_user(username='chahkandi', password='Password123!')
        self.chahkandi_user.roles.add(self.admin_role)

        self.ali_user = User.objects.create_user(username='ali', password='Password123!')
        self.ali_user.roles.add(self.admin_role)

        self.client = APIClient()

    # ── ۱. تست‌های پورسانت و فیلتر فروشنده ──────────────────────────────────
    def test_put_seller_commission_persists_and_get_filters_by_seller(self):
        """تست اینکه PUT پورسانت تغییرات را ماندگار می‌کند و GET بعدی فقط همان فروشنده را برمی‌گرداند"""
        self.client.force_authenticate(user=self.admin)

        new_milestones = [
            {'target_amount': 250000000, 'reward_amount': 3000000},
            {'target_amount': 400000000, 'reward_amount': 7000000}
        ]
        put_payload = {
            'seller': str(self.seller1.id),
            'model_type': 'THRESHOLD_SURPLUS',
            'threshold_amount': 120000000,
            'surplus_percentage': 3.5,
            'reward_active': True,
            'reward_milestones': new_milestones
        }

        # 1. ارسال PUT
        res_put = self.client.put(
            f'/api/seller-commissions/{self.config1.id}/',
            data=put_payload,
            format='json'
        )
        self.assertEqual(res_put.status_code, status.HTTP_200_OK)
        self.assertEqual(res_put.data['reward_milestones'], new_milestones)

        # 2. بررسی مستقیم دیتابیس
        self.config1.refresh_from_db()
        self.assertEqual(self.config1.reward_milestones, new_milestones)
        self.assertEqual(self.config1.threshold_amount, Decimal('120000000'))

        # 3. ارسال GET با فیلتر seller مربوط به seller1
        res_get1 = self.client.get(f'/api/seller-commissions/?seller={self.seller1.id}')
        self.assertEqual(res_get1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_get1.data), 1)
        self.assertEqual(res_get1.data[0]['seller'], self.seller1.id)
        self.assertEqual(res_get1.data[0]['reward_milestones'], new_milestones)

        # 4. ارسال GET با فیلتر seller مربوط به seller2
        res_get2 = self.client.get(f'/api/seller-commissions/?seller={self.seller2.id}')
        self.assertEqual(res_get2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_get2.data), 1)
        self.assertEqual(res_get2.data[0]['seller'], self.seller2.id)
        self.assertEqual(res_get2.data[0]['reward_milestones'], [])

    # ── ۲. تست‌های نمایش حواله‌ها برای انباردار ──────────────────────────────
    def test_warehouse_user_can_view_all_transfers(self):
        """تست اینکه کاربر انباردار تمام حواله‌های انتقالی بین شعب را مشاهده می‌کند"""
        # ایجاد ۲ حواله بین شعب
        transfer1 = BranchTransfer.objects.create(
            source_branch='BEHESHTI',
            destination_branch='SEPIDEH',
            transfer_date=datetime.date.today(),
            driver_name='راننده ۱',
            source_cashier=self.cashier,
            sender_supervisor=self.sup1,
            receiver_supervisor=self.sup2,
            status='PENDING_SENDER'
        )
        transfer2 = BranchTransfer.objects.create(
            source_branch='MODARRES',
            destination_branch='KAJESTAN',
            transfer_date=datetime.date.today(),
            driver_name='راننده ۲',
            source_cashier=self.cashier,
            sender_supervisor=self.sup1,
            receiver_supervisor=self.sup2,
            status='PENDING_RECEIVER'
        )

        # ورود به عنوان کاربر انباردار
        self.client.force_authenticate(user=self.warehouse_user)
        res = self.client.get('/api/transfers/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = {str(item['id']) for item in res.data}
        self.assertIn(str(transfer1.id), returned_ids)
        self.assertIn(str(transfer2.id), returned_ids)
        self.assertEqual(len(res.data), 2)

    # ── ۳. تست‌های دسترسی فقط‌خواندنی نقدینگی برای chahkandi و ali ─────────────
    def test_chahkandi_and_ali_read_only_in_liquidity_and_denied_on_writes(self):
        """تست اینکه کاربران chahkandi و ali در نقدینگی فقط‌خواندنی هستند ولی بقیه دسترسی‌هایشان حفظ است"""
        # ایجاد یک شارژ تستی
        charge = LiquidityDailyCharge.objects.create(
            date=datetime.date.today(),
            beheshti_pos=Decimal('10000000'),
            created_by=self.admin
        )

        for user in [self.chahkandi_user, self.ali_user]:
            self.client.force_authenticate(user=user)

            # ۱. دسترسی خواندن (GET) به شارژ روزانه -> مجاز
            res_get_charge = self.client.get('/api/liquidity/daily-charges/')
            self.assertEqual(res_get_charge.status_code, status.HTTP_200_OK)

            # ۲. دسترسی خواندن به درآمد روزانه -> مجاز
            res_get_rev = self.client.get('/api/liquidity/daily-revenue/')
            self.assertEqual(res_get_rev.status_code, status.HTTP_200_OK)

            # ۳. دسترسی خواندن به چک‌ها -> مجاز
            res_get_checks = self.client.get('/api/liquidity/checks/')
            self.assertEqual(res_get_checks.status_code, status.HTTP_200_OK)

            # ۴. دسترسی خواندن به کارت‌ها -> مجاز
            res_get_cards = self.client.get('/api/liquidity/cards/')
            self.assertEqual(res_get_cards.status_code, status.HTTP_200_OK)

            # ۵. تلاش برای نوشتن (POST) در شارژ روزانه -> باید خطای ۴۰۳ بدهد
            payload = {
                'date': str(datetime.date.today() - datetime.timedelta(days=1)),
                'beheshti_pos': 5000000,
                'description': 'تست شارژ غیرمجاز'
            }
            res_post_charge = self.client.post('/api/liquidity/daily-charges/', data=payload, format='json')
            self.assertEqual(res_post_charge.status_code, status.HTTP_403_FORBIDDEN)
            self.assertIn('دسترسی مشاهده', str(res_post_charge.data))

            # ۶. تلاش برای حذف یا ویرایش شارژ روزانه -> خطای ۴۰۳
            res_del = self.client.delete(f'/api/liquidity/daily-charges/{charge.id}/')
            self.assertEqual(res_del.status_code, status.HTTP_403_FORBIDDEN)

            # ۷. دسترسی به بخش‌های دیگر سامانه (مثلاً لیست کاربران یا انتقال‌ها) به عنوان ادمین -> بدون محدودیت
            res_users = self.client.get('/api/users/')
            self.assertEqual(res_users.status_code, status.HTTP_200_OK)

    def test_login_returns_can_modify_liquidity_flag(self):
        """تست اینکه اندپوینت لاگین فیلد can_modify_liquidity را با مقدار صحیح برمی‌گرداند"""
        # کاربر عادی ادمین
        res_admin = self.client.post('/api/auth/token/', data={'username': 'main_admin', 'password': 'Password123!'})
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        self.assertTrue(res_admin.data['can_modify_liquidity'])

        # کاربر chahkandi
        res_chahkandi = self.client.post('/api/auth/token/', data={'username': 'chahkandi', 'password': 'Password123!'})
        self.assertEqual(res_chahkandi.status_code, status.HTTP_200_OK)
        self.assertFalse(res_chahkandi.data['can_modify_liquidity'])

        # کاربر ali
        res_ali = self.client.post('/api/auth/token/', data={'username': 'ali', 'password': 'Password123!'})
        self.assertEqual(res_ali.status_code, status.HTTP_200_OK)
        self.assertFalse(res_ali.data['can_modify_liquidity'])
