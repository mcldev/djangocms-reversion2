
# Generated by Django 1.11 on 2018-08-09 15:01
from __future__ import unicode_literals

from django.db import migrations
import versionfield


class Migration(migrations.Migration):

    dependencies = [
        ('djangocms_reversion2', '0005_auto_20180807_1250'),
    ]

    operations = [
        migrations.AddField(
            model_name='pageversion',
            name='version_id',
            field=versionfield.VersionField(blank=True, null=True, verbose_name='Version'),
        ),
    ]