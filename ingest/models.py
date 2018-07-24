from django.db import models
from django.contrib.auth.models import User
from django.utils.html import format_html

import django_filters
import django_tables2 as tables
from django_tables2.utils import A  # alias for Accessor

from .fieldlist import attrs as image_metadata_fields


class Collection(models.Model):
    """ A grouping of one or more datasets and associated metadata. """
    def __str__(self):
        return self.name

    # Required and the user should supply these
    name = models.CharField(max_length=256, unique=True)
    description = models.TextField()
    AI = 'AI'
    CSHL = 'CSHL'
    USC = 'USC'
    PITT = 'PITT'
    ORGANIZATION_CHOICES = (
        (CSHL, 'Cold Spring Harbor Laboratory'),
        (USC, 'University of Southern California'),
        (AI, 'Allen Institute'),
        (PITT, 'University of Pittsburgh'),
    )
    organization_name = models.CharField(
        max_length=256,
        choices=ORGANIZATION_CHOICES,
        default=AI,
        help_text=(
            "The institution where the data generator/submitter or other "
            "responsible person resides.")
    )
    lab_name = models.CharField(
        max_length=256, help_text="The lab or department subgroup")
    project_funder_id = models.CharField(
        max_length=256, help_text="The grant number")

    # Optional fields. The user doesn't need to supply these.
    project_funder = models.CharField(
        max_length=256, blank=True, default="NIH")

    # These fields are required but the user shouldn't control these
    data_path = models.CharField(max_length=256)
    # "locked" is used to prevent submitted data from being changed
    locked = models.BooleanField(default=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, blank=True, null=True)
    # This is how we're initially tracking validation. Ultimately, we'll
    # probably want to break up validation into multiple tasks (e.g. checking
    # dataset size, verifying valid TIFF/JPEG2000 files, etc), in which case
    # we'll probably want to set up a one-to-many relationship w/ task IDs.
    celery_task_id = models.CharField(max_length=256)
    NOT_SUBMITTED = 'NOT_SUBMITTED'
    SUCCESS = 'SUCCESS'
    PENDING = 'PENDING'
    FAILED = 'FAILED'
    STATUS_CHOICES = (
        (NOT_SUBMITTED, 'Not submitted'),
        (SUCCESS, 'Success'),
        (PENDING, 'Pending'),
        (FAILED, 'Failed'),
    )
    status = models.CharField(
        max_length=256,
        choices=STATUS_CHOICES,
        default=NOT_SUBMITTED,
    )


class CollectionTable(tables.Table):
    """ The table used in the collection list. """

    # We use a collection's id as a link to the corresponding collection
    # detail.
    id = tables.LinkColumn(
        'ingest:collection_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        attrs={'a': {'class': "btn btn-info", 'role': "button"}})
    description = tables.Column()

    def render_project_description(self, value):
        """ Ellipsize the project description if it's too long. """
        limit_len = 32
        value = value if len(value) < limit_len else value[:limit_len] + "…"
        return value

    def render_locked(self, value):
        if value:
            value = format_html('<i class="fa fa-lock"></i>')
        else:
            value = format_html('<i class="fa fa-unlock"></i>')
        return value

    def render_status(self, value):
        """ Show the status as an icon. """
        if value == "Not submitted":
            value = format_html('<i class="fa fa-minus" style="color:blue"></i>')
        elif value == "Success":
            value = format_html('<i class="fa fa-check" style="color:green"></i>')
        elif value == "Pending":
            value = format_html('<i class="fa fa-clock" style="color:yellow"></i>')
        elif value == "Failed":
            value = format_html('<i class="fa fa-exclamation-circle" style="color:red"></i>')
        return value

    class Meta:
        model = Collection
        exclude = ['celery_task_id', 'user']
        template_name = 'ingest/bootstrap_ingest.html'


class CollectionFilter(django_filters.FilterSet):
    """ Interactively filter display locked or unlocked collecions. """

    class Meta:
        model = Collection
        fields = ['status']


class ImageMetadata(models.Model):
    # The meat of the image metadata bookkeeping. This is all the relevant
    # information about a given set of imaging data.
    def __str__(self):
        return self.project_name

    # This can be used for multiple drop down choices
    UNKNOWN = 'Unknown'

    # Required and the user should supply these
    project_name = models.CharField(
        max_length=256,
        help_text=('If this is Minitatlas data, begin this field with '
                   '"MINIATLAS:". The project name does not have to be the '
                   'same as the NIH project name.'))
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    project_description = models.TextField()
    background_strain = models.CharField(
        max_length=256, help_text="e.g. C57BL/6J")
    image_filename_pattern = models.CharField(max_length=256)
    directory = models.CharField(
        max_length=4096,
        help_text=(
            "relative to the landing zone, the top level directory name of "
            "this dataset, e.g. './mouse_dataset_0001'"),
    )

    # These fields are required but the user shouldn't control these
    #
    # "locked" is used to prevent submitted data from being changed
    locked = models.BooleanField(default=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True, blank=True)
    last_edited = models.DateTimeField(auto_now=True, blank=True)

    # Optional fields. The user doesn't need to supply these.
    taxonomy_name = models.CharField(max_length=256, blank=True, default="")
    transgenic_line_name = models.CharField(
        max_length=256, blank=True, default="")
    age = models.IntegerField(blank=True, null=True)
    DAY = 'DAY'
    WEEK = 'WEEK'
    MONTH = 'MONTH'
    AGE_UNIT_CHOICES = (
        (DAY, 'Day'),
        (WEEK, 'Week'),
        (MONTH, 'Month'),
        (UNKNOWN, 'Unknown'),
    )
    age_unit = models.CharField(
        max_length=256,
        choices=AGE_UNIT_CHOICES,
        default=UNKNOWN)
    MALE = 'MALE'
    FEMALE = 'FEMALE'
    SEX_CHOICES = (
        (MALE, 'Male'),
        (FEMALE, 'Female'),
        (UNKNOWN, 'Unknown'),
    )
    sex = models.CharField(
        max_length=256,
        choices=SEX_CHOICES,
        default=UNKNOWN,
    )
    organ = models.CharField(max_length=256, blank=True, default="Brain")
    organ_substructure = models.CharField(
        max_length=256,
        blank=True,
        default="Whole brain",
        help_text="e.g. hippocampus, prefrontal cortex")
    assay = models.CharField(
        max_length=256,
        blank=True,
        default="",
        help_text="e.g. smFISH, fMOST, MouseLight")
    CORONAL = 'CORONAL'
    SAGITTAL = 'SAGITTAL'
    AXIAL = 'AXIAL'
    SLICING_DIRECTION_CHOICES = (
        (CORONAL, 'Coronal'),
        (SAGITTAL, 'Sagittal'),
        (AXIAL, 'Axial'),
        (UNKNOWN, 'Unknown'),
    )
    slicing_direction = models.CharField(
        max_length=256,
        choices=SLICING_DIRECTION_CHOICES,
        default=UNKNOWN,
    )
    MAPZ = 'MAPZ'
    MAPXY = 'MAPXY'
    MAPYX = 'MAPYX'
    MAPXYZ = 'MAPXYZ'
    MAPYXZ = 'MAPYXZ'
    MAPZXY = 'MAPZXY'
    MAPZYX = 'MAPZYX'
    MAP_CHOICES = (
        (MAPZ, 'Map Z'),
        (MAPXY, 'Map XY'),
        (MAPYX, 'Map YX'),
        (MAPXYZ, 'Map XYZ'),
        (MAPYXZ, 'Map YXZ'),
        (MAPZXY, 'Map ZXY'),
        (MAPZYX, 'Map ZYX'),
        (MAPZYX, 'Map ZYX'),
        (UNKNOWN, 'Unknown'),
    )
    image_map_style = models.CharField(
        max_length=256,
        choices=MAP_CHOICES,
        default=UNKNOWN,
    )

    PROC1 = 'ORIGINAL_CAPTURE_UNPROCESSED'
    PROC2 = 'ORIGINAL_CAPTURE_AUTOSTITCHED'
    PROC3 = 'FULL_CAPTURE_REFORMATED'
    PROC4 = 'FULL_CAPTURE_STITCHED_REFORMATTED'
    PROC5 = 'PROCESSED'
    PROCESSING_CHOICES = (
        (PROC1, 'Original Capture Unprocessed'),
        (PROC2, 'Original Capture Autostitched'),
        (PROC3, 'Full Capture Reformatted'),
        (PROC4, 'Full Capture Stitched Reformatted'),
        (PROC5, 'Processed'),
        (UNKNOWN, 'Unknown'),
    )

    processing_level = models.CharField(
        max_length=256,
        choices=PROCESSING_CHOICES,
        default=UNKNOWN,
    )


class ImageMetadataTable(tables.Table):
    """ The table used in the image metadata list. """

    # We use the metadata's id as a link to the corresponding collection
    # detail.
    id = tables.LinkColumn(
        'ingest:image_metadata_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        attrs={'a': {'class': "btn btn-info", 'role': "button"}}
    )
    project_description = tables.Column()

    def render_project_description(self, value):
        """ Ellipsize the project description if it's too long. """
        limit_len = 32
        value = value if len(value) < limit_len else value[:limit_len] + "…"
        return value

    def render_locked(self, value):
        if value:
            value = format_html('<i class="fa fa-lock"></i>')
        else:
            value = format_html('<i class="fa fa-unlock"></i>')
        return value

    class Meta:
        model = ImageMetadata
        template_name = 'ingest/bootstrap_ingest.html'
        # the order of "sequence" determines the ordering of the columns
        sequence = ['id'] + image_metadata_fields

    # This gives us a checkbox for every piece of metadata, thereby allowing
    # the user to select and delete them (assuming they're unlocked).
    selection = tables.CheckBoxColumn(
        accessor="pk",
        attrs={"th__input": {"onclick": "toggle(this)"}},
        orderable=False)
