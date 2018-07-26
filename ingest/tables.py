from django.utils.html import format_html

from .models import Collection
from .models import ImageMetadata
import django_tables2 as tables
from django_tables2.utils import A  # alias for Accessor


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

    def render_project_name(self, value):
        """ Ellipsize the project name if it's too long. """
        limit_len = 32
        value = value if len(value) < limit_len else value[:limit_len] + "…"
        return value

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
        # XXX: we should store this information in field_list
        exclude = [
            'user',
            'background_strain',
            'taxonomy_name',
            'transgenic_line_name',
            'age',
            'age_unit',
            'sex',
            'organ',
            'organ_substructure',
            'assay',
            'slicing_direction',
            'image_map_style',
            'processing_level',
            'image_filename_pattern',
        ]
        # the order of "sequence" determines the ordering of the columns
        sequence = [
            'id',
            'collection',
            'project_name',
            'project_description',
            'directory',
            'date_created',
            'last_edited',
            'locked'
        ]

    # This gives us a checkbox for every piece of metadata, thereby allowing
    # the user to select and delete them (assuming they're unlocked).
    selection = tables.CheckBoxColumn(
        accessor="pk",
        attrs={"th__input": {"onclick": "toggle(this)"}},
        orderable=False)
