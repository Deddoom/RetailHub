from django.db import migrations, models
from django.db import connection


def add_fields_if_not_exists(apps, schema_editor):
    with connection.cursor() as cursor:

        # is_profile_completed در core_customuser
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='core_customuser' AND column_name='is_profile_completed'
        """)
        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE core_customuser ADD COLUMN is_profile_completed boolean NOT NULL DEFAULT false"
            )

        # purchase_types در core_customer
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='core_customer' AND column_name='purchase_types'
        """)
        if not cursor.fetchone():
            cursor.execute(
                "ALTER TABLE core_customer ADD COLUMN purchase_types jsonb NOT NULL DEFAULT '[]'::jsonb"
            )

        # حذف last_purchase_type از core_customer
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='core_customer' AND column_name='last_purchase_type'
        """)
        if cursor.fetchone():
            cursor.execute(
                "ALTER TABLE core_customer DROP COLUMN last_purchase_type"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_checklist_log_system'),
    ]

    operations = [
        migrations.RunPython(add_fields_if_not_exists, migrations.RunPython.noop),
    ]