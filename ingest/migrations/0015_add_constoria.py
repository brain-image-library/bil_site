# Generated by Django 3.2.18 on 2023-03-06 15:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0014_metadataversion'),
    ]

    operations = [
        migrations.CreateModel(
            name='Consortium',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('short_name', models.CharField(max_length=256)),
                ('long_name', models.CharField(max_length=1000)),
            ],
        ),
        migrations.CreateModel(
            name='ProjectConsortium',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('constorium', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.consortium')),
                ('project', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.project')),
            ],
        ),
    ]
