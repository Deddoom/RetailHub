from django.db import migrations


def fix_claim_seller(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='core_claim' AND column_name='seller_id'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='core_claim' AND column_name='seller'
                    ) THEN
                        ALTER TABLE core_claim RENAME COLUMN seller_id TO seller;
                    END IF;
                END $$;
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_claim_seller_to_charfield'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.RunPython(fix_claim_seller, migrations.RunPython.noop),
            ],
        ),
    ]
