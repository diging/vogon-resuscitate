# Generated by Django 2.2.20 on 2024-08-27 18:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('external_accounts', '0006_citespheregroup_sync_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='CitesphereItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('authors', models.TextField(help_text='JSON format of authors list')),
                ('editors', models.TextField(blank=True, help_text='JSON format of editors list', null=True)),
                ('itemType', models.CharField(max_length=100)),
                ('publicationTitle', models.CharField(blank=True, max_length=255, null=True)),
                ('volume', models.CharField(blank=True, max_length=50, null=True)),
                ('issue', models.CharField(blank=True, max_length=50, null=True)),
                ('pages', models.CharField(blank=True, max_length=50, null=True)),
                ('date', models.DateTimeField()),
                ('url', models.URLField(blank=True, null=True)),
                ('abstractNote', models.TextField(blank=True, null=True)),
                ('journalAbbreviation', models.CharField(blank=True, max_length=100, null=True)),
                ('doi', models.CharField(blank=True, max_length=100, null=True)),
                ('issn', models.CharField(blank=True, max_length=100, null=True)),
                ('extra', models.TextField(blank=True, null=True)),
                ('dateAdded', models.DateTimeField()),
                ('dateModified', models.DateTimeField(blank=True, null=True)),
                ('collection', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='items', to='external_accounts.CitesphereCollection')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='external_accounts.CitesphereGroup')),
            ],
        ),
    ]