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
        
    # پشتیبانی از دستور اختصاصی seed کماکان به صورت استاندارد داخل فریمورک
    if len(sys.argv) > 1 and sys.argv[1] == 'seed':
        import django
        django.setup()
        from django.core.management import call_command
        from core.models import CustomUser, Seller, Customer, Checklist, Task

        print("[!] Preparing database tables (Migrating)...")
        call_command('migrate', run_syncdb=True, interactive=False)
        
        print("[!] Seeding initial data rows into database...")
        admin_user, created = CustomUser.objects.get_or_create(
            username='admin', defaults={'role': 'ADMIN', 'branch': 'دفتر مرکزی', 'is_staff': True, 'is_superuser': True}
        )
        if created: admin_user.set_password('admin1234'); admin_user.save()

        cashier_user, created = CustomUser.objects.get_or_create(
            username='cashier', defaults={'role': 'CASHIER', 'branch': 'شعبه پاسداران'}
        )
        if created: cashier_user.set_password('cashier1234'); cashier_user.save()

        seller, _ = Seller.objects.get_or_create(name='امیر قاسمی', defaults={'phone': '09120001122', 'branch': 'شعبه پاسداران'})
        customer, _ = Customer.objects.get_or_create(phone='09154445566', defaults={'name': 'علیرضا فتاحی', 'primary_goods': 'NEHAL'})
        
        print("[+] Seeding process finished successfully!")
        return

    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()