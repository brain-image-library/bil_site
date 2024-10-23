# Generated by Django 3.2.18 on 2024-10-16 14:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0034_auto_20240920_1612'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dataset',
            name='methods',
            field=models.CharField(blank=True, max_length=256),
        ),
        migrations.CreateModel(
            name='DatasetTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tag', models.CharField(max_length=256)),
                ('bil_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ingest.bil_id')),
                ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags', to='ingest.dataset')),
            ],
        ),
    ]
