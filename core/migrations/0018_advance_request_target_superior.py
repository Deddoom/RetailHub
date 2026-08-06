import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_advancerequest_advancerequestlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='advancerequest',
            name='target_superior',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name='received_advance_requests',
                verbose_name='بالادستی انتخاب‌شده توسط کاربر',
            ),
        ),
    ]
