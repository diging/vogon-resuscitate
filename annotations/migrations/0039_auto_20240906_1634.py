# Generated by Django 2.2.20 on 2024-09-06 16:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0038_importedcitesphereitem_user'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='text',
            name='repository',
        ),
        migrations.RemoveField(
            model_name='text',
            name='repository_source_id',
        ),
    ]