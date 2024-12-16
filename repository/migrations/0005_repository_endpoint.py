# Generated by Django 2.2.20 on 2024-10-03 17:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('repository', '0004_remove_repository_configuration'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='endpoint',
            field=models.URLField(default='https://diging-dev.asu.edu/citesphere-review'),
            preserve_default=False,
        ),
    ]
