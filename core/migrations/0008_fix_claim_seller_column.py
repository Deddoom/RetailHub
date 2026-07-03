from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_claim_seller_to_charfield'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='claim',
                    name='seller',
                    field=models.CharField(max_length=150),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
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
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
    ]
