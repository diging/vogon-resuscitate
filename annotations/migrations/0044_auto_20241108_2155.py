# Generated by Django 2.2.20 on 2024-11-08 21:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0043_auto_20241108_2154'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vogonuser',
            name='vogon_admin',
            field=models.BooleanField(default=False, help_text='This field indicates if the user has admin permissions within the application without Django admin access.'),
        ),
    ]
