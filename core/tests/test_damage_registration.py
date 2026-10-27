# -*- coding: utf-8 -*-
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from core.models import CustomUser, Role, DamageRegistration, DamageItem, DamageRegistrationLog


class DamageRegistrationWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # تعریف نقش‌ها
        self.role_admin, _ = Role.objects.get_or_create(code='ADMIN')
        self.role_sales_manager, _ = Role.objects.get_or_create(code='SALES_MANAGER')
        self.role_supervisor, _ = Role.objects.get_or_create(code='SUPERVISOR')
        self.role_warehouse, _ = Role.objects.get_or_create(code='WAREHOUSE')
        self.role_stat, _ = Role.objects.get_or_create(code='STATISTICIAN')
        self.role_finance, _ = Role.objects.get_or_create(code='FINANCIAL_MANAGER')
        self.role_user, _ = Role.objects.get_or_create(code='USER')

        # تعریف کاربران
        self.admin = CustomUser.objects.create_user(username='admin_user', is_superuser=True)
        self.admin.roles.add(self.role_admin)

        self.sales_manager = CustomUser.objects.create_user(username='sales_mgr', first_name='مدیر', last_name='فروش')
        self.sales_manager.roles.add(self.role_sales_manager)

        self.supervisor1 = CustomUser.objects.create_user(username='supervisor1', first_name='سرپرست', last_name='یک')
        self.supervisor1.roles.add(self.role_supervisor)

        self.supervisor2 = CustomUser.objects.create_user(username='supervisor2', first_name='سرپرست', last_name='دو')
        self.supervisor2.roles.add(self.role_supervisor)

        self.warehouse = CustomUser.objects.create_user(username='warehouse_user', first_name='انباردار', last_name='اصلی')
        self.warehouse.roles.add(self.role_warehouse)

        self.finance = CustomUser.objects.create_user(username='finance_user', first_name='مدیر', last_name='مالی')
        self.finance.roles.add(self.role_finance)

        self.normal_user = CustomUser.objects.create_user(username='normal_user')
        self.normal_user.roles.add(self.role_user)

    def test_damage_creation_permissions(self):
        """فقط سرپرست یا ادمین اجازه ثبت ضایعات را دارند و وضعیت اولیه در انتظار مدیر فروش است"""
        payload = {
            "date": "2026-10-22",
            "branch": "شعبه بهشتی",
            "reason": "BREAKAGE",
            "culprit": "واحد توزیع",
            "description": "شکستگی در مسیر انتقال",
            "items": [
                {"item_name": "گلدان بزرگ", "quantity": 2, "unit_price": "50000.00"}
            ]
        }

        # کاربر عادی نباید بتواند ثبت کند
        self.client.force_authenticate(user=self.normal_user)
        res_fail = self.client.post('/api/damage-registrations/', payload, format='json')
        self.assertEqual(res_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("created_by", res_fail.data)

        # سرپرست می‌تواند ثبت کند
        self.client.force_authenticate(user=self.supervisor1)
        res_ok = self.client.post('/api/damage-registrations/', payload, format='json')
        self.assertEqual(res_ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_ok.data['status'], 'PENDING_SALES_MANAGER')
        self.assertEqual(str(res_ok.data['supervisor']), str(self.supervisor1.id))
        self.assertEqual(len(res_ok.data['items']), 1)

    def test_five_stage_approval_workflow(self):
        """تست گردش کار کامل ۵ مرحله‌ای: سرپرست -> مدیر فروش -> انباردار -> مدیریت -> مدیر مالی"""
        # ۱. ثبت توسط سرپرست
        self.client.force_authenticate(user=self.supervisor1)
        create_res = self.client.post('/api/damage-registrations/', {
            "date": "2026-10-22",
            "branch": "شعبه بهشتی",
            "reason": "PEST",
            "description": "آفت زدگی در گلخانه",
            "items": [
                {"item_name": "گیاه سانسوریا", "quantity": 5, "unit_price": "120000.00"}
            ]
        }, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        reg_id = create_res.data['id']
        self.assertEqual(create_res.data['status'], 'PENDING_SALES_MANAGER')

        # ۲. مرحله ۱: بررسی مدیر فروش
        # کاربر انباردار قبل از مدیر فروش نباید بتواند تایید انبار را بزند
        self.client.force_authenticate(user=self.warehouse)
        wh_early = self.client.post(f'/api/damage-registrations/{reg_id}/warehouse-review/', {
            "action": "approve"
        }, format='json')
        self.assertEqual(wh_early.status_code, status.HTTP_400_BAD_REQUEST)

        # سرپرست دسترسی به تایید مدیر فروش ندارد
        self.client.force_authenticate(user=self.supervisor1)
        fail_sm = self.client.post(f'/api/damage-registrations/{reg_id}/sales-manager-review/', {
            "action": "approve",
            "note": "تلاش غیرمجاز"
        }, format='json')
        self.assertEqual(fail_sm.status_code, status.HTTP_403_FORBIDDEN)

        # مدیر فروش تایید می‌کند
        self.client.force_authenticate(user=self.sales_manager)
        sm_res = self.client.post(f'/api/damage-registrations/{reg_id}/sales-manager-review/', {
            "action": "approve",
            "note": "تایید اولیه مدیر فروش"
        }, format='json')
        self.assertEqual(sm_res.status_code, status.HTTP_200_OK)

        reg = DamageRegistration.objects.get(id=reg_id)
        self.assertEqual(reg.status, 'PENDING_WAREHOUSE')
        self.assertEqual(reg.sales_manager_reviewer, self.sales_manager)
        self.assertEqual(reg.sales_manager_note, "تایید اولیه مدیر فروش")
        self.assertIsNotNone(reg.sales_manager_reviewed_at)

        # ۳. مرحله ۲: بررسی انباردار
        self.client.force_authenticate(user=self.warehouse)
        wh_res = self.client.post(f'/api/damage-registrations/{reg_id}/warehouse-review/', {
            "action": "approve",
            "note": "رویت شد و تایید است"
        }, format='json')
        self.assertEqual(wh_res.status_code, status.HTTP_200_OK)

        reg.refresh_from_db()
        self.assertEqual(reg.status, 'PENDING_MANAGEMENT')
        self.assertEqual(reg.warehouse_reviewer, self.warehouse)
        self.assertEqual(reg.warehouse_note, "رویت شد و تایید است")
        self.assertIsNotNone(reg.warehouse_reviewed_at)

        # ۴. مرحله ۳: بررسی مدیریت
        self.client.force_authenticate(user=self.admin)
        mgmt_res = self.client.post(f'/api/damage-registrations/{reg_id}/management-review/', {
            "action": "approve"
        }, format='json')
        self.assertEqual(mgmt_res.status_code, status.HTTP_200_OK)

        reg.refresh_from_db()
        self.assertEqual(reg.status, 'PENDING_FINANCIAL')
        self.assertEqual(reg.management_reviewer, self.admin)
        self.assertIsNotNone(reg.management_reviewed_at)

        # ۵. مرحله ۴: بررسی مدیر مالی
        self.client.force_authenticate(user=self.finance)
        fin_res = self.client.post(f'/api/damage-registrations/{reg_id}/financial-review/', {
            "action": "approve",
            "note": "تایید نهایی جهت خروج از حساب‌ها"
        }, format='json')
        self.assertEqual(fin_res.status_code, status.HTTP_200_OK)

        reg.refresh_from_db()
        self.assertEqual(reg.status, 'APPROVED')
        self.assertEqual(reg.financial_reviewer, self.finance)
        self.assertEqual(reg.financial_note, "تایید نهایی جهت خروج از حساب‌ها")
        self.assertIsNotNone(reg.financial_reviewed_at)

        # بررسی لاگ‌های تولیدشده
        logs = reg.logs.all().order_by('created_at')
        stages = [log.stage for log in logs]
        self.assertIn('SUBMIT', stages)
        self.assertIn('SALES_MANAGER', stages)
        self.assertIn('WAREHOUSE', stages)
        self.assertIn('MANAGEMENT', stages)
        self.assertIn('FINANCIAL', stages)

    def test_visibility_permissions(self):
        """تست دسترسی‌ها: سرپرست فقط مال خودش، مدیر فروش و انباردار و مدیر مالی و ادمین به همه دسترسی دارند"""
        reg1 = DamageRegistration.objects.create(
            date="2026-10-20",
            branch="شعبه بهشتی",
            reason="BREAKAGE",
            created_by=self.supervisor1,
            supervisor=self.supervisor1,
            status="PENDING_SALES_MANAGER"
        )
        reg2 = DamageRegistration.objects.create(
            date="2026-10-21",
            branch="شعبه مدرس",
            reason="LIGHT",
            created_by=self.supervisor2,
            supervisor=self.supervisor2,
            status="PENDING_SALES_MANAGER"
        )

        # ۱. سرپرست ۱ فقط رکورد ۱ را می‌بیند
        self.client.force_authenticate(user=self.supervisor1)
        res1 = self.client.get('/api/damage-registrations/')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        ids1 = [r['id'] for r in res1.data]
        self.assertIn(str(reg1.id), ids1)
        self.assertNotIn(str(reg2.id), ids1)

        # ۲. سرپرست ۲ فقط رکورد ۲ را می‌بیند
        self.client.force_authenticate(user=self.supervisor2)
        res2 = self.client.get('/api/damage-registrations/')
        ids2 = [r['id'] for r in res2.data]
        self.assertNotIn(str(reg1.id), ids2)
        self.assertIn(str(reg2.id), ids2)

        # ۳. مدیر فروش همه را می‌بیند
        self.client.force_authenticate(user=self.sales_manager)
        res_sm = self.client.get('/api/damage-registrations/')
        ids_sm = [r['id'] for r in res_sm.data]
        self.assertIn(str(reg1.id), ids_sm)
        self.assertIn(str(reg2.id), ids_sm)

        # ۴. انباردار همه را می‌بیند
        self.client.force_authenticate(user=self.warehouse)
        res_wh = self.client.get('/api/damage-registrations/')
        ids_wh = [r['id'] for r in res_wh.data]
        self.assertIn(str(reg1.id), ids_wh)
        self.assertIn(str(reg2.id), ids_wh)

        # ۵. مدیر مالی همه را می‌بیند
        self.client.force_authenticate(user=self.finance)
        res_fin = self.client.get('/api/damage-registrations/')
        ids_fin = [r['id'] for r in res_fin.data]
        self.assertIn(str(reg1.id), ids_fin)
        self.assertIn(str(reg2.id), ids_fin)

        # ۶. ادمین همه را می‌بیند
        self.client.force_authenticate(user=self.admin)
        res_adm = self.client.get('/api/damage-registrations/')
        ids_adm = [r['id'] for r in res_adm.data]
        self.assertIn(str(reg1.id), ids_adm)
        self.assertIn(str(reg2.id), ids_adm)

    def test_cancel_action(self):
        """سرپرست ثبت‌کننده می‌تواند تا قبل از تایید مدیر فروش رکورد را لغو کند"""
        reg = DamageRegistration.objects.create(
            date="2026-10-20",
            branch="شعبه بهشتی",
            reason="BREAKAGE",
            created_by=self.supervisor1,
            supervisor=self.supervisor1,
            status="PENDING_SALES_MANAGER"
        )
        self.client.force_authenticate(user=self.supervisor1)
        cancel_res = self.client.post(f'/api/damage-registrations/{reg.id}/cancel/')
        self.assertEqual(cancel_res.status_code, status.HTTP_200_OK)

        reg.refresh_from_db()
        self.assertEqual(reg.status, 'CANCELLED')
