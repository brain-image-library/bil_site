# Generated by Django 3.1.14 on 2022-04-25 12:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0007_auto_20220420_1426'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataset',
            name='specimen_ingest_method_4',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
