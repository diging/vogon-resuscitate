# Generated by Django 2.2.20 on 2024-09-05 22:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('annotations', '0036_importedcitesphereitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='importedcitesphereitem',
            name='project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='citesphere_items', to='annotations.TextCollection'),
        ),
    ]