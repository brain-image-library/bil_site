# Generated by Django 3.2.18 on 2024-10-23 18:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0040_alter_dataset_technicalinfo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='methods',
            field=models.CharField(blank=True, max_length=2000),
        ),
    ]
