from django.db import models
from django.contrib.auth.models import User
from django.utils.html import format_html

import django_tables2 as tables
from django_tables2.utils import A  # alias for Accessor


class ImageData(models.Model):
    # Contains information about where the actual data will be stored.
    #
    # The user doesn't supply any of this. It is all generated automatically at
    # the click of a button.
    def __str__(self):
        return self.data_path

    data_path = models.CharField(max_length=256)
    locked = models.BooleanField(default=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)


class ImageDataTable(tables.Table):
    id = tables.LinkColumn(
        'ingest:image_data_dirs_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        attrs={'a': {'class': "btn btn-info", 'role': "button"}})

    class Meta:
        model = ImageData
        template_name = 'ingest/bootstrap_ingest.html'


class ImageMetadata(models.Model):
    # The meat of the image metadata bookkeeping. This is all the relevant
    # information about a given set of imaging data. Currently, it is 1:1 but
    # eventually multiple pieces of metadata will be able to go with ImageData.
    def __str__(self):
        return self.project_name

    # Required and the user should supply these
    AI = 'AI'
    CSHL = 'CSHL'
    USC = 'USC'
    ORGANIZATION_CHOICES = (
        (CSHL, 'Cold Spring Harbor Laboratory'),
        (USC, 'University of Southern California'),
        (AI, 'Allen Institute'),
    )
    organization_name = models.CharField(
        max_length=256,
        choices=ORGANIZATION_CHOICES,
        default=AI,
    )
    project_name = models.CharField(
        max_length=256, help_text='The name of your project')
    project_description = models.TextField()
    project_funder_id = models.CharField(max_length=256)
    background_strain = models.CharField(max_length=256)
    image_filename_pattern = models.CharField(max_length=256)
    lab_name = models.CharField(max_length=256)
    # XXX: thinking we should prolly just get this from the user info
    submitter_email = models.CharField(max_length=256)

    # Required but the user shouldn't control these
    locked = models.BooleanField(default=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, blank=True)
    last_edited = models.DateTimeField(auto_now=True, blank=True)

    # Optional fields. The user doesn't need to supply these.
    project_funder = models.CharField(max_length=256, blank=True, default="")
    taxonomy_name = models.CharField(max_length=256, blank=True, default="")
    transgenic_line_name = models.CharField(
        max_length=256, blank=True, default="")
    age = models.IntegerField(blank=True)
    age_unit = models.CharField(max_length=256, blank=True, default="")
    MALE = 'MALE'
    FEMALE = 'FEMALE'
    SEX_CHOICES = (
        (MALE, 'Male'),
        (FEMALE, 'Female'),
    )
    sex = models.CharField(
        max_length=256,
        choices=SEX_CHOICES,
        default=FEMALE,
    )
    organ = models.CharField(max_length=256, blank=True, default="")
    organ_substructure = models.CharField(
        max_length=256, blank=True, default="")
    assay = models.CharField(max_length=256, blank=True, default="")
    slicing_direction = models.CharField(
        max_length=256, blank=True, default="")


class ImageMetadataTable(tables.Table):
    id = tables.LinkColumn(
        'ingest:image_metadata_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        attrs={'a': {'class': "btn btn-info", 'role': "button"}}
    )
    project_description = tables.Column()

    def render_project_description(self, value):
        limit_len = 32
        value = value if len(value) < limit_len else value[:limit_len] + "…"
        return value

    class Meta:
        model = ImageMetadata
        template_name = 'ingest/bootstrap_ingest.html'

    amend = tables.CheckBoxColumn(verbose_name=('Amend'), accessor='pk')


class Collection(models.Model):
    # A collection is how we tie metadata to a specific set of data.
    def __str__(self):
        return self.name

    name = models.CharField(max_length=256)
    description = models.TextField()
    metadata = models.ForeignKey(
        ImageMetadata,
        on_delete=models.SET_NULL, blank=True, null=True)
    data_path = models.ForeignKey(
        ImageData,
        on_delete=models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, blank=True, null=True)


class CollectionTable(tables.Table):
    id = tables.LinkColumn(
        'ingest:collection_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        attrs={'a': {'class': "btn btn-info", 'role': "button"}})
    description = tables.Column()

    def render_project_description(self, value):
        limit_len = 32
        value = value if len(value) < limit_len else value[:limit_len] + "…"
        return value

    class Meta:
        model = Collection
        template_name = 'ingest/bootstrap_ingest.html'
