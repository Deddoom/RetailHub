from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_report_system'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='total_purchase_amount',
            field=models.DecimalField(
                max_digits=12,
                decimal_places=2,
                default=Decimal('0.00')
            ),
        ),
    ]