# Generated by Django 3.1.7 on 2021-05-10 20:11

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Collection',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256, unique=True)),
                ('description', models.TextField()),
                ('organization_name', models.CharField(help_text='The institution where the data generator/submitter or other responsible person resides.', max_length=256)),
                ('lab_name', models.CharField(help_text='The lab or department subgroup', max_length=256)),
                ('project_funder_id', models.CharField(help_text='The grant number', max_length=256)),
                ('project_funder', models.CharField(blank=True, default='NIH', max_length=256)),
                ('modality', models.CharField(blank=True, default='NIH', max_length=256)),
                ('bil_uuid', models.CharField(max_length=256)),
                ('data_path', models.CharField(max_length=256)),
                ('locked', models.BooleanField(default=False)),
                ('celery_task_id_submission', models.CharField(max_length=256)),
                ('celery_task_id_validation', models.CharField(max_length=256)),
                ('submission_status', models.CharField(choices=[('NOT_SUBMITTED', 'Not submitted'), ('SUCCESS', 'Success'), ('PENDING', 'Pending'), ('FAILED', 'Failed')], default='NOT_SUBMITTED', max_length=256)),
                ('validation_status', models.CharField(choices=[('NOT_VALIDATED', 'Not validated'), ('SUCCESS', 'Success'), ('PENDING', 'Pending'), ('FAILED', 'Failed')], default='NOT_VALIDATED', max_length=256)),
                ('collection_type', models.CharField(max_length=256)),
            ],
        ),
        migrations.CreateModel(
            name='Funder',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256)),
                ('funding_reference_identifier', models.CharField(max_length=256)),
                ('funding_reference_identifier_type', models.CharField(max_length=256)),
                ('award_number', models.CharField(max_length=256)),
                ('award_title', models.CharField(max_length=256)),
                ('grant_number', models.CharField(max_length=256)),
            ],
        ),
        migrations.CreateModel(
            name='People',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256)),
                ('orcid', models.CharField(max_length=256)),
                ('affiliation', models.CharField(max_length=256)),
                ('affiliation_identifier', models.CharField(max_length=256)),
                ('auth_user_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('funded_by', models.CharField(max_length=256)),
                ('is_biccn', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='UUID',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('useduuid', models.CharField(max_length=256, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='ProjectPeople',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_pi', models.BooleanField(default=False)),
                ('is_po', models.BooleanField(default=False)),
                ('doi_role', models.CharField(max_length=256)),
                ('people_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.people')),
                ('project_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ingest.project')),
            ],
        ),
        migrations.CreateModel(
            name='ProjectFunders',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('funder_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ingest.funder')),
                ('project_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ingest.project')),
            ],
        ),
        migrations.CreateModel(
            name='ImageMetadata',
            fields=[
                 ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project_name', models.CharField(help_text='The project name does not have to be the same as the NIH project name.', max_length=256)),
                ('project_description', models.TextField()),
                ('background_strain', models.CharField(help_text='e.g. C57BL/6J', max_length=256)),
                ('image_filename_pattern', models.CharField(max_length=256)),
                ('directory', models.CharField(help_text="relative to the landing zone, the top level directory name of this dataset, e.g. './mouse_dataset_0001'", max_length=4096)),
                ('locked', models.BooleanField(default=False)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('last_edited', models.DateTimeField(auto_now=True)),
                ('taxonomy_name', models.CharField(blank=True, default='', max_length=256)),
                ('transgenic_line_name', models.CharField(blank=True, default='', max_length=256)),
                ('age', models.IntegerField(blank=True, null=True)),
                ('age_unit', models.CharField(choices=[('DAY', 'Day'), ('WEEK', 'Week'), ('MONTH', 'Month'), ('Unknown', 'Unknown')], default='Unknown', max_length=256)),
                ('sex', models.CharField(choices=[('MALE', 'Male'), ('FEMALE', 'Female'), ('Unknown', 'Unknown')], default='Unknown', max_length=256)),
                ('organ', models.CharField(blank=True, default='Brain', max_length=256)),
                ('organ_substructure', models.CharField(blank=True, default='Whole brain', help_text='e.g. hippocampus, prefrontal cortex', max_length=256)),
                ('assay', models.CharField(blank=True, default='', help_text='e.g. smFISH, fMOST, MouseLight', max_length=256)),
                ('slicing_direction', models.CharField(choices=[('CORONAL', 'Coronal'), ('SAGITTAL', 'Sagittal'), ('AXIAL', 'Axial'), ('Unknown', 'Unknown')], default='Unknown', max_length=256)),
                ('image_map_style', models.CharField(choices=[('MAPZ', 'Map Z'), ('MAPXY', 'Map XY'), ('MAPYX', 'Map YX'), ('MAPXYZ', 'Map XYZ'), ('MAPYXZ', 'Map YXZ'), ('MAPZXY', 'Map ZXY'), ('MAPZYX', 'Map ZYX'), ('MAPZYX', 'Map ZYX'), ('Unknown', 'Unknown')], default='Unknown', max_length=256)),
                ('processing_level', models.CharField(choices=[('ORIGINAL_CAPTURE_UNPROCESSED', 'Original Capture Unprocessed'), ('ORIGINAL_CAPTURE_AUTOSTITCHED', 'Original Capture Autostitched'), ('FULL_CAPTURE_REFORMATED', 'Full Capture Reformatted'), ('FULL_CAPTURE_STITCHED_REFORMATTED', 'Full Capture Stitched Reformatted'), ('PROCESSED', 'Processed'), ('Unknown', 'Unknown')], default='Unknown', max_length=256)),
                ('collection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ingest.collection')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='EventsLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notes', models.CharField(max_length=256)),
                ('timestamp', models.DateTimeField()),
                ('event_type', models.CharField(choices=[('mail_tapes_to_bil', 'Mail Tapes To BIL'), ('tapes_received', 'Tapes Received'), ('tapes_ready_for_qc', 'Tapes Ready For QC'), ('move_to_collection', 'Move To Collection'), ('request_brainball', 'Request Brainball'), ('Mail_brainball_from_bil', 'Mail Brainball From BIL'), ('mail_brainball_to_bil', 'Mail Brainball To BIL'), ('received_brainball', 'Received Brainball'), ('collection_created', 'Collection Created'), ('metadata_uploaded', 'Metadata Uploaded'), ('request_validation', 'Request Validation'), ('request_submission', 'Request Submission'), ('request_embargo', 'Request Embargo'), ('collection_public', 'Collection Public'), ('request_withdrawal', 'Request Withdrawal')], default='', max_length=64)),
                ('collection_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.collection')),
                ('people_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.people')),
                ('project_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.project')),
            ],
        ),
        migrations.CreateModel(
            name='DescriptiveMetadata',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('locked', models.BooleanField(default=False)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('last_edited', models.DateTimeField(auto_now=True)),
                ('sample_id', models.CharField(max_length=256)),
                ('organism_type', models.CharField(max_length=256)),
                ('organism_ncbi_taxonomy_id', models.CharField(max_length=256)),
                ('transgenetic_line_information', models.CharField(max_length=256)),
                ('modality', models.CharField(blank=True, max_length=256, null=True)),
                ('method', models.CharField(max_length=256)),
                ('technique', models.CharField(max_length=256)),
                ('anatomical_structure', models.CharField(max_length=256)),
                ('total_processed_cells', models.CharField(max_length=256)),
                ('organization', models.CharField(max_length=256)),
                ('lab', models.CharField(max_length=256)),
                ('investigator', models.CharField(max_length=256)),
                ('grant_number', models.CharField(max_length=256)),
                ('dataset_uuid', models.CharField(blank=True, max_length=256, null=True)),
                ('r24_name', models.CharField(max_length=256)),
                ('r24_directory', models.CharField(max_length=256)),
                ('collection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ingest.collection')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='CollectionGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256)),
                ('project_id', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='ingest.project')),
            ],
        ),
        migrations.AddField(
            model_name='collection',
            name='collection_group_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ingest.collectiongroup'),
        ),
        migrations.AddField(
            model_name='collection',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
    ]
