# Generated by Django 2.2.20 on 2024-09-05 23:11

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0037_importedcitesphereitem_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='importedcitesphereitem',
            name='user',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='imported_citesphere_data', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
