# Generated by Django 2.2.20 on 2024-10-29 18:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0042_relationset_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='relationset',
            name='pending',
        ),
    ]