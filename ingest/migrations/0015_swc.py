# Generated by Django 3.2.18 on 2023-05-25 16:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0014_metadataversion'),
    ]

    operations = [
        migrations.CreateModel(
            name='SWC',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tracingFile', models.CharField(blank=True, max_length=256, null=True)),
                ('sourceData', models.CharField(blank=True, max_length=256, null=True)),
                ('sourceDataSample', models.CharField(blank=True, max_length=256, null=True)),
                ('sourceDataSubmission', models.CharField(blank=True, max_length=256, null=True)),
                ('coordinates', models.CharField(blank=True, max_length=256, null=True)),
                ('coordinatesRegistration', models.CharField(blank=True, max_length=256, null=True)),
                ('brainRegion', models.CharField(blank=True, max_length=256, null=True)),
                ('brainRegionAtlas', models.CharField(blank=True, max_length=256, null=True)),
                ('brainRegionAtlasName', models.CharField(blank=True, max_length=256, null=True)),
                ('brainRegionAxonalProjection', models.CharField(blank=True, max_length=256, null=True)),
                ('brainRegionDendriticProjection', models.CharField(blank=True, max_length=256, null=True)),
                ('neuronType', models.CharField(blank=True, max_length=256, null=True)),
                ('segmentTags', models.CharField(blank=True, max_length=256, null=True)),
                ('proofreadingLevel', models.CharField(blank=True, max_length=256, null=True)),
                ('notes', models.TextField()),
                ('data_set', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.dataset')),
                ('sheet', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.sheet')),
            ],
        ),
    ]
