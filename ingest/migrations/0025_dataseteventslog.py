# Generated by Django 3.2.18 on 2023-12-04 01:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0024_alter_dataset_socialmedia'),
    ]

    operations = [
        migrations.CreateModel(
            name='DatasetEventsLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notes', models.CharField(max_length=256)),
                ('timestamp', models.DateTimeField()),
                ('event_type', models.CharField(choices=[('uploaded', 'Uploaded'), ('validated', 'Validated'), ('curated', 'Curated'), ('doi', 'DOI'), ('public', 'Public')], default='', max_length=64)),
                ('collection_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.collection')),
                ('dataset_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.dataset')),
                ('project_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.project')),
            ],
        ),
    ]