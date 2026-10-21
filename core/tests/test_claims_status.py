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
