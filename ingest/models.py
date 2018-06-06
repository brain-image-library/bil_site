from django.db import models
from django.contrib.auth.models import User
from django.utils.html import format_html

import django_tables2 as tables
from django_tables2.utils import A  # alias for Accessor

import uuid


class ImageData(models.Model):
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
        attrs= {'a': {'class': "btn btn-info", 'role': "button"}})
    class Meta:
        model = ImageData
        template_name = 'ingest/bootstrap_ingest.html'


class ImageMetadata(models.Model):
    def __str__(self):
        return self.project_name
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
    project_name = models.CharField(max_length=256)
    project_description = models.TextField()
    project_funder_id = models.CharField(max_length=256)
    background_strain = models.CharField(max_length=256)
    image_filename_pattern = models.CharField(max_length=256)
    locked = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(auto_now=True)
    last_edited = models.DateTimeField(auto_now_add=True)


class ImageMetadataTable(tables.Table):
    id = tables.LinkColumn(
        'ingest:image_metadata_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        attrs= {'a': {'class': "btn btn-info", 'role': "button"}})
    project_description = tables.Column()

    def render_project_description(self, value):
        limit_len = 32
        value = value if len(value) < limit_len else value[:limit_len]+"…"
        return value

    class Meta:
        model = ImageMetadata
        template_name = 'ingest/bootstrap_ingest.html'


class Collection(models.Model):
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
    date_created = models.DateTimeField(auto_now=True)
    last_edited = models.DateTimeField(auto_now_add=True)


class CollectionTable(tables.Table):
    id = tables.LinkColumn(
        'ingest:collection_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        attrs= {'a': {'class': "btn btn-info", 'role': "button"}})
    description = tables.Column()

    def render_project_description(self, value):
        limit_len=32
        value = value if len(value) < limit_len else value[:limit_len]+"…"
        return value

    class Meta:
        model = Collection
        template_name = 'ingest/bootstrap_ingest.html'
