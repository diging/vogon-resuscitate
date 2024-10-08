# Generated by Django 2.2.20 on 2024-09-06 16:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('repository', '0002_remove_repository_configuration'),
        ('annotations', '0039_auto_20240906_1634'),
    ]

    operations = [
        migrations.AddField(
            model_name='text',
            name='repository',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='texts', to='repository.Repository'),
        ),
        migrations.AddField(
            model_name='text',
            name='repository_source_id',
            field=models.IntegerField(blank=True, default=-1, null=True),
        ),
    ]
