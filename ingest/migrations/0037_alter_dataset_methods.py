# Generated by Django 3.2.18 on 2024-10-16 14:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0036_alter_datasettag_tag'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='methods',
            field=models.CharField(blank=True, max_length=3000),
        ),
    ]