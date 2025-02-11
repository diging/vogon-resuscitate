# Generated by Django 2.2.20 on 2024-11-08 21:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0041_delete_importedcitesphereitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='vogonuser',
            name='vogon_admin',
            field=models.BooleanField(default=False, help_text='Indicates if the user has admin permissions within the application without Django admin access.'),
        ),
    ]
