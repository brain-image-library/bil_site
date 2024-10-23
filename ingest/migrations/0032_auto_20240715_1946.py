# Generated by Django 3.2.18 on 2024-07-15 19:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0031_datasettag_bil_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collection',
            name='celery_task_id_submission',
            field=models.CharField(max_length=256, null=True),
        ),
        migrations.AlterField(
            model_name='collection',
            name='celery_task_id_validation',
            field=models.CharField(max_length=256, null=True),
        ),
        migrations.DeleteModel(
            name='DatasetTag',
        ),
    ]
