# Generated by Django 3.2.13 on 2022-07-13 18:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0011_auto_20220602_1409'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='title',
            field=models.CharField(max_length=500),
        ),
        migrations.AlterField(
            model_name='publication',
            name='citation',
            field=models.CharField(blank=True, max_length=1500),
        ),
    ]
