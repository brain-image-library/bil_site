# Generated by Django 3.1.7 on 2021-06-22 17:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='name',
            field=models.CharField(default='Project Name', max_length=256),
        ),
        migrations.CreateModel(
            name='DataGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_group_list_id', models.IntegerField()),
                ('dm_id', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ingest.descriptivemetadata')),
            ],
        ),
    ]