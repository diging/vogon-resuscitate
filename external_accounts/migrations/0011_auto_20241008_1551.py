# Generated by Django 2.2.20 on 2024-10-08 15:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0041_delete_importedcitesphereitem'),
        ('external_accounts', '0010_auto_20240827_1855'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='citespheregroup',
            name='citesphere_accounts',
        ),
        migrations.RemoveField(
            model_name='citesphereitem',
            name='collection',
        ),
        migrations.RemoveField(
            model_name='citesphereitem',
            name='group',
        ),
        migrations.DeleteModel(
            name='CitesphereCollection',
        ),
        migrations.DeleteModel(
            name='CitesphereGroup',
        ),
        migrations.DeleteModel(
            name='CitesphereItem',
        ),
    ]