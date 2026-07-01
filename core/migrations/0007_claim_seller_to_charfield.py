from django.db import migrations, models
from django.db import connection


def convert_seller_to_charfield(apps, schema_editor):
    with connection.cursor() as cursor:
        # اول یه ستون متنی موقت بساز
        cursor.execute("""
            ALTER TABLE core_claim 
            ADD COLUMN seller_text varchar(150) NOT NULL DEFAULT ''
        """)
        # مقدار نام فروشنده رو از جدول seller کپی کن
        cursor.execute("""
            UPDATE core_claim cc
            SET seller_text = s.name
            FROM core_seller s
            WHERE cc.seller_id = s.id
        """)
        # ستون FK قدیمی رو حذف کن
        cursor.execute("ALTER TABLE core_claim DROP COLUMN seller_id")
        # ستون موقت رو rename کن
        cursor.execute("ALTER TABLE core_claim RENAME COLUMN seller_text TO seller_id")


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_fix_customer_and_user'),
    ]

    operations = [
        migrations.RunPython(convert_seller_to_charfield, migrations.RunPython.noop),
    ]
