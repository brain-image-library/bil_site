from django.db import models
import django_tables2 as tables
from django_tables2.utils import A  # alias for Accessor
import uuid

class MinimalImgMetadata(models.Model):
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
    linked_to_data = models.BooleanField(default=False)


class MinimalImgTable(tables.Table):
    id = tables.LinkColumn('ingest:detail', args=[A('pk')])
    project_description = tables.Column()

    def render_project_description(self, value):
        limit_len = 32
        value = value if len(value) < limit_len else value[:limit_len]+"…"
        return value

    class Meta:
        model = MinimalImgMetadata
        template_name = 'ingest/bootstrap_ingest.html'


class Collection(models.Model):
    def __str__(self):
        return self.name
    uniqueid = models.UUIDField(primary_key = True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=256)
    description = models.TextField()
    metadata = models.ForeignKey(
        MinimalImgMetadata,
        on_delete=models.SET_NULL,
        blank=True,
        null=True)
    data_path = models.CharField(default="")
