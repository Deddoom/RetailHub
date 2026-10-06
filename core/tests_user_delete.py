# -*- coding: utf-8 -*-
from django.test import TestCase
from rest_framework.test import APIClient
from decimal import Decimal
import datetime

from core.models import CustomUser, Role, LiquidityExpense


class UserSmartDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # نقش ادمین
        self.role_admin, _ = Role.objects.get_or_create(code='ADMIN')
        self.role_user, _ = Role.objects.get_or_create(code='USER')
        self.role_supervisor, _ = Role.objects.get_or_create(code='SUPERVISOR')

        # ادمین سیستم
        self.admin = CustomUser.objects.create_user(
            username='admin_master',
            password='adminpassword123',
            first_name='مدیر',
            last_name='کل'
        )
        self.admin.roles.add(self.role_admin)
        self.client.force_authenticate(user=self.admin)

        # ۱. کاربر بدون سابقه وابسته
        self.user_clean = CustomUser.objects.create_user(
            username='clean_user_01',
            password='password123',
            first_name='کاربر',
            last_name='بدون‌سابقه'
        )
        self.user_clean.roles.add(self.role_user)

        # ۲. کاربر با سابقه وابسته
        self.user_with_records = CustomUser.objects.create_user(
            username='user_with_data_02',
            password='password123',
            first_name='کاربر',
            last_name='دارای‌سابقه'
        )
        self.user_with_records.roles.add(self.role_supervisor)

        # ایجاد رکورد وابسته محافظت‌شده (LiquidityExpense) برای کاربر دوم
        self.expense = LiquidityExpense.objects.create(
            title='هزینه ثبت شده توسط کاربر',
            category='OTHER',
            amount=Decimal('5000000.00'),
            due_date=datetime.date.today(),
            created_by=self.user_with_records
        )

    def test_self_deletion_forbidden(self):
        """ادمین نباید بتواند حساب کاربری خودش را حذف کند"""
        res = self.client.delete(f'/api/users/{self.admin.id}/')
        self.assertEqual(res.status_code, 400)
        self.assertIn("نمی‌توانید حساب کاربری خودتان را حذف کنید", res.data.get('error', ''))

    def test_hard_delete_user_without_dependents(self):
        """کاربر بدون سابقه وابسته به طور کامل از دیتابیس پاک می‌شود"""
        clean_user_id = self.user_clean.id
        res = self.client.delete(f'/api/users/{clean_user_id}/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data.get('soft_deleted'))
        self.assertFalse(CustomUser.objects.filter(id=clean_user_id).exists())

    def test_soft_delete_user_with_dependents(self):
        """کاربر با سوابق وابسته به صورت هوشمند حذف نرم می‌شود بدون ایجاد خطای 400"""
        user_id = self.user_with_records.id
        old_username = self.user_with_records.username

        res = self.client.delete(f'/api/users/{user_id}/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get('soft_deleted'))

        self.user_with_records.refresh_from_db()
        self.assertTrue(self.user_with_records.is_deleted)
        self.assertFalse(self.user_with_records.is_active)
        self.assertIsNotNone(self.user_with_records.deleted_at)
        self.assertEqual(self.user_with_records.original_username, old_username)
        self.assertTrue(self.user_with_records.username.startswith('deleted_'))

        # اسناد مالی وابسته سالم و مرتبط باقی می‌مانند
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.created_by_id, user_id)

    def test_reregister_original_username_after_deletion(self):
        """پس از حذف کاربر، نام کاربری و شماره قبلی برای ثبت مجدد آزاد می‌شود"""
        old_username = self.user_with_records.username
        res = self.client.delete(f'/api/users/{self.user_with_records.id}/')
        self.assertEqual(res.status_code, 200)

        # ساخت مجدد کاربر با همان نام کاربری آزاد شده
        new_user = CustomUser.objects.create_user(
            username=old_username,
            password='newpassword123',
            first_name='شخص',
            last_name='جدید'
        )
        self.assertIsNotNone(new_user.id)
        self.assertEqual(new_user.username, old_username)

    def test_deleted_user_excluded_from_listings(self):
        """کاربر حذف شده در لیست‌های عادی نمایش داده نمی‌شود مگر با پارامتر include_deleted"""
        self.client.delete(f'/api/users/{self.user_with_records.id}/')

        # لیست عادی
        res = self.client.get('/api/users/')
        self.assertEqual(res.status_code, 200)
        user_list = res.data if isinstance(res.data, list) else res.data.get('results', [])
        user_ids = [u['id'] for u in user_list]
        self.assertNotIn(str(self.user_with_records.id), user_ids)

        # لیست سرپرستان
        res_sup = self.client.get('/api/users/supervisors/')
        self.assertEqual(res_sup.status_code, 200)
        sup_ids = [s['id'] for s in res_sup.data]
        self.assertNotIn(str(self.user_with_records.id), sup_ids)

        # لیست با پارامتر include_deleted=true
        res_all = self.client.get('/api/users/?include_deleted=true')
        self.assertEqual(res_all.status_code, 200)
        all_list = res_all.data if isinstance(res_all.data, list) else res_all.data.get('results', [])
        all_ids = [u['id'] for u in all_list]
        self.assertIn(str(self.user_with_records.id), all_ids)

    def test_deleted_user_cannot_login(self):
        """کاربر حذف شده امکان ورود به سیستم ندارد"""
        old_username = self.user_with_records.username
        self.client.delete(f'/api/users/{self.user_with_records.id}/')

        # خروج احراز هویت قبلی کلاینت برای تست لاگین
        self.client.force_authenticate(user=None)

        # تلاش با نام کاربری اصلی قدیمی -> نامعتبر است (چون تغییر نام یافته)
        res_old = self.client.post('/api/auth/token/', {
            'username': old_username,
            'password': 'password123'
        })
        self.assertEqual(res_old.status_code, 401)

        # تلاش با نام کاربری تغییریافته deleted_* -> غیرفعال است (403)
        self.user_with_records.refresh_from_db()
        res_deleted = self.client.post('/api/auth/token/', {
            'username': self.user_with_records.username,
            'password': 'password123'
        })
        self.assertEqual(res_deleted.status_code, 403)

    def test_restore_soft_deleted_user(self):
        """بازیابی موفق کاربر حذف شده توسط ادمین"""
        user_id = self.user_with_records.id
        old_username = self.user_with_records.username
        self.client.delete(f'/api/users/{user_id}/')

        # بازیابی
        res_restore = self.client.post(f'/api/users/{user_id}/restore/')
        self.assertEqual(res_restore.status_code, 200)

        self.user_with_records.refresh_from_db()
        self.assertFalse(self.user_with_records.is_deleted)
        self.assertTrue(self.user_with_records.is_active)
        self.assertIsNone(self.user_with_records.deleted_at)
        self.assertEqual(self.user_with_records.username, old_username)
        self.assertIsNone(self.user_with_records.original_username)

    def test_restore_conflict_when_username_taken(self):
        """عدم امکان بازیابی در صورت اشغال بودن نام کاربری توسط کاربر دیگر"""
        user_id = self.user_with_records.id
        old_username = self.user_with_records.username
        self.client.delete(f'/api/users/{user_id}/')

        # کاربر دیگری همان نام کاربری را ثبت می‌کند
        CustomUser.objects.create_user(
            username=old_username,
            password='otherpassword'
        )

        # تلاش برای بازیابی باید خطای 400 برگرداند
        res_restore = self.client.post(f'/api/users/{user_id}/restore/')
        self.assertEqual(res_restore.status_code, 400)
        self.assertIn("توسط کاربر دیگری در حال استفاده است", res_restore.data.get('error', ''))
