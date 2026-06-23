#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django standard framework is not installed.") from exc
        
    if len(sys.argv) > 1 and sys.argv[1] == 'seed':
        import django
        django.setup()
        
        from django.core.management import call_command
        from core.models import CustomUser, Seller, Customer, Role # انتقال ایمپورت به بعد از ستاپ

        print("[!] Preparing database tables (Migrating)...")
        call_command('migrate', run_syncdb=True, interactive=False)

        print("[!] Seeding initial data rows into database...")
    
        # ساخت نقش‌ها
        role_codes = [
            'ADMIN', 'CASHIER', 'FINANCIAL_MANAGER', 'EXECUTIVE_MANAGER', 
            'SUPERVISOR', 'ACCOUNTANT', 'STATISTICIAN', 'USER'
        ]
        roles = {}
        for code in role_codes:
            roles[code], _ = Role.objects.get_or_create(code=code)

        # دیتای کاربران تستی (username, password, branch, role_obj, is_superuser)
        seed_users = [
            ('admin', 'admin1234', 'شعبه بهشتی', roles['ADMIN'], True),
            ('cashier', 'cashier1234', 'شعبه مدرس', roles['CASHIER'], False),
            ('fin_manager', 'fin1234', 'شعبه بهشتی', roles['FINANCIAL_MANAGER'], False),
            ('exec_manager', 'exec1234', 'شعبه مدرس', roles['EXECUTIVE_MANAGER'], False),
            ('supervisor', 'super1234', 'شعبه سپیده', roles['SUPERVISOR'], False),
            ('accountant', 'acc1234', 'شعبه بهشتی', roles['ACCOUNTANT'], False),
            ('statistician', 'stat1234', 'شعبه کاجستان', roles['STATISTICIAN'], False),
            ('normal_user', 'user1234', 'شعبه مدرس', roles['USER'], False),
        ]

        for username, password, branch, role_obj, is_super in seed_users:
            user, created = CustomUser.objects.get_or_create(
                username=username,
                defaults={'branch': branch, 'is_staff': is_super, 'is_superuser': is_super}
            )
            if created:
                user.set_password(password)
                user.save()
            user.roles.add(role_obj)

        Seller.objects.get_or_create(
            name='امیر قاسمی',
            defaults={'phone': '09120001122', 'branch': 'شعبه مدرس'}
        )
        Customer.objects.get_or_create(
            phone='09154445566',
            defaults={'name': 'علیرضا فتاحی', 'primary_goods': 'NEHAL'}
        )

        print("[+] Seeding process finished successfully!")
        return

    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()