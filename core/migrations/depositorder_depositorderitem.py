from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid
 
 
class Migration(migrations.Migration):
 
    dependencies = [
        # نام migration قبلی خودتون رو اینجا بذارید
        ('core', '0001_initial'),
    ]
 
    operations = [
        migrations.CreateModel(
            name='DepositOrder',
            fields=[
                ('id',                     models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at',             models.DateTimeField(auto_now_add=True)),
                ('branch',                 models.CharField(max_length=100)),
                ('delivery_date',          models.DateField()),
                ('total_amount',           models.DecimalField(decimal_places=2, max_digits=12)),
                ('discount_amount',        models.DecimalField(decimal_places=2, default='0.00', max_digits=12)),
                ('deposit_paid',           models.DecimalField(decimal_places=2, default='0.00', max_digits=12)),
                ('remaining_debt',         models.DecimalField(decimal_places=2, default='0.00', max_digits=12)),
                ('deposit_payment_method', models.CharField(blank=True, max_length=30, null=True,
                    choices=[('CASH', 'نقدی'), ('CARD_TO_CARD', 'کارت به کارت'), ('CHEQUE', 'چک'), ('POS', 'کارتخوان'), ('OTHER', 'سایر')])),
                ('debt_payment_method',    models.CharField(blank=True, max_length=30, null=True,
                    choices=[('CASH', 'نقدی'), ('CARD_TO_CARD', 'کارت به کارت'), ('CHEQUE', 'چک'), ('POS', 'کارتخوان'), ('COMBINED', 'ترکیبی'), ('OTHER', 'سایر')])),
                ('status',                 models.CharField(choices=[('PENDING', 'در انتظار تحویل'), ('DELIVERED', 'تحویل داده شده'), ('CANCELLED', 'لغو شده')], default='PENDING', max_length=20)),
                ('description',            models.TextField(blank=True, null=True)),
                ('created_by',             models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='deposit_orders_created', to=settings.AUTH_USER_MODEL)),
                ('customer',               models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='deposit_orders', to='core.customer')),
                ('seller',                 models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='deposit_orders', to='core.seller')),
                ('sale',                   models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deposit_order', to='core.sale')),
            ],
        ),
        migrations.CreateModel(
            name='DepositOrderItem',
            fields=[
                ('id',          models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('item_name',   models.CharField(max_length=150)),
                ('quantity',    models.IntegerField()),
                ('unit_price',  models.DecimalField(decimal_places=2, max_digits=12)),
                ('total_price', models.DecimalField(decimal_places=2, editable=False, max_digits=12)),
                ('order',       models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='core.depositorder')),
            ],
        ),
    ]
