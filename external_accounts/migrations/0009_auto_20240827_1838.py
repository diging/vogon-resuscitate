# Generated by Django 2.2.20 on 2024-08-27 18:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('external_accounts', '0008_auto_20240827_1838'),
    ]

    operations = [
        migrations.AlterField(
            model_name='citesphereitem',
            name='key',
            field=models.CharField(max_length=100),
        ),
    ]
