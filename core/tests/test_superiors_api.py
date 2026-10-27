# -*- coding: utf-8 -*-
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from core.models import CustomUser, Role


class SuperiorsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.role_admin, _ = Role.objects.get_or_create(code='ADMIN')
        self.role_sales_manager, _ = Role.objects.get_or_create(code='SALES_MANAGER')
        self.role_supervisor, _ = Role.objects.get_or_create(code='SUPERVISOR')
        self.role_seller, _ = Role.objects.get_or_create(code='SELLER_STAFF')

        # تعریف ساختار درختی سازمانی
        # فروشنده -> سرپرست -> مدیر فروش -> ادمین
        self.admin = CustomUser.objects.create_user(username='admin_boss', is_superuser=True)
        self.admin.roles.add(self.role_admin)

        self.sales_manager = CustomUser.objects.create_user(username='sales_head', first_name='سرپرست', last_name='فروش کل')
        self.sales_manager.roles.add(self.role_sales_manager)
        self.sales_manager.superiors.add(self.admin)

        self.supervisor = CustomUser.objects.create_user(username='branch_supervisor', first_name='سرپرست', last_name='شعبه')
        self.supervisor.roles.add(self.role_supervisor)
        self.supervisor.superiors.add(self.sales_manager)

        self.seller = CustomUser.objects.create_user(username='seller_person', first_name='علی', last_name='فروشنده')
        self.seller.roles.add(self.role_seller)
        self.seller.superiors.add(self.supervisor)

    def test_model_get_all_superiors(self):
        """بررسی متد BFS مدل get_all_superiors برای یافتن کل زنجیره بالادستی‌ها"""
        all_sups = self.seller.get_all_superiors()
        sup_ids = {u.id for u in all_sups}
        self.assertIn(self.supervisor.id, sup_ids)
        self.assertIn(self.sales_manager.id, sup_ids)
        self.assertIn(self.admin.id, sup_ids)
        self.assertEqual(len(all_sups), 3)

    def test_direct_superiors_api(self):
        """فراخوانی اندپوینت superiors به صورت پیش‌فرض بالادستی‌های مستقیم را برمی‌گرداند"""
        self.client.force_authenticate(user=self.seller)
        res = self.client.get('/api/users/superiors/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['username'], 'branch_supervisor')

    def test_chain_superiors_api(self):
        """فراخوانی اندپوینت با chain=true کل هرم بالادستی‌ها را بازمی‌گرداند"""
        self.client.force_authenticate(user=self.seller)
        res = self.client.get('/api/users/superiors/?chain=true')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        usernames = {u['username'] for u in res.data}
        self.assertEqual(usernames, {'branch_supervisor', 'sales_head', 'admin_boss'})

    def test_superiors_user_id_param(self):
        """ادمین می‌تواند با پارامتر user_id بالادستی‌های هر کاربری را مشاهده کند"""
        # کاربر عادی اجازه ندارد برای دیگران کوئری بزند
        self.client.force_authenticate(user=self.seller)
        fail_res = self.client.get(f'/api/users/superiors/?user_id={self.supervisor.id}')
        self.assertEqual(fail_res.status_code, status.HTTP_403_FORBIDDEN)

        # ادمین مجاز است
        self.client.force_authenticate(user=self.admin)
        ok_res = self.client.get(f'/api/users/superiors/?user_id={self.seller.id}')
        self.assertEqual(ok_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(ok_res.data), 1)
        self.assertEqual(ok_res.data[0]['username'], 'branch_supervisor')
