from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Collection
from .models import ImageMetadata
from .models import DescriptiveMetadata
from .models import Sheet, Project, ProjectConsortium, Specimen, BIL_Specimen_ID, SpecimenLinkage
import django_tables2 as tables
from django_tables2.utils import A  # alias for Accessor


class SubmitValidateCollectionTable(tables.Table):
    """ The table used in the collection list. """

    # We use a collection's id as a link to the corresponding collection
    # detail.
    id = tables.LinkColumn(
        'ingest:collection_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<button type="button" class="btn btn-primary">Select</button>'))
        #text=format_html('<span class="glyphicon glyphicon-cog">ABCD</span>'),
        #attrs={'a': {'class': "btn btn-info", 'role': "button"}})
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

    def render_submission_status(self, value):
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

    def render_validation_status(self, value):
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
        exclude = ['celery_task_id_submission', 'celery_task_id_validation', 'user']
        template_name = 'ingest/bootstrap_ingest.html'


class CollectionTable(tables.Table):
    """ The table used in the collection list. """

    # We use a collection's id as a link to the corresponding collection
    # detail.
    id = tables.LinkColumn(
        'ingest:collection_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<button type="button" class="btn btn-primary">Select</button>'))
        #text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        #attrs={'a': {'class': "btn btn-info", 'role': "button"}})
    description = tables.Column()

    bican_ids_button = tables.Column(
        verbose_name="",
        accessor='most_recent_sheet_pk',
        orderable=False,
        empty_values=(),
    )

    def __init__(self, *args, **kwargs):
        super(CollectionTable, self).__init__(*args, **kwargs)
        self.dynamic_args()

    def dynamic_args(self):
        for record in self.data:
            most_recent_sheet = Sheet.objects.filter(collection_id=record.id).last()
            specimens = Specimen.objects.filter(sheet = most_recent_sheet)
            bil_specimen_ids = BIL_Specimen_ID.objects.filter(specimen_id__in=specimens)
            linked_bil_specimen_ids = SpecimenLinkage.objects.filter(specimen_id__in=bil_specimen_ids)

            if most_recent_sheet:
                if record.submission_status == 'SUCCESS':
                    record.most_recent_sheet_pk = mark_safe('<div class="alert alert-success" role="alert">Data Public</div>')
                elif ProjectConsortium.objects.filter(project=record.project, consortium__short_name='BICAN').exists():
                    if linked_bil_specimen_ids.exists():
                        record.most_recent_sheet_pk = mark_safe('<a href="{}" class="btn btn-info">Request Publication</a>'.format(reverse('ingest:submit_request_collection_list')))
                    else:
                        record.most_recent_sheet_pk = mark_safe('<a href="{}" class="btn btn-primary">Add Bican IDs</a>'.format(reverse('ingest:bican_id_upload', args=[most_recent_sheet.pk])))
                else:
                    record.most_recent_sheet_pk = mark_safe('<a href="{}" class="btn btn-info">Request Publication</a>'.format(reverse('ingest:submit_request_collection_list')))
            else:
                record.most_recent_sheet_pk = mark_safe('<a href="{}" class="btn btn-danger">Needs Metadata</a>'.format(reverse('ingest:descriptive_metadata_upload', args=[record.id])))

    class Meta:
        model = Collection
        exclude = ['celery_task_id_submission', 'celery_task_id_validation', 'user', 'modality']
        template_name = 'django_tables2/bootstrap.html'


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

    def render_submission_status(self, value):
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

    def render_validation_status(self, value):
        """ Show the status as an icon. """
        if value == "Not submitted":
            value = format_html('<button type="button" class="btn btn-primary">Not Submitted</button>')
            #value = format_html('<i class="fa fa-minus" style="color:blue"></i>')
        elif value == "Success":
            value = format_html('<i class="fa fa-check" style="color:green"></i>')
        elif value == "Pending":
            value = format_html('<i class="fa fa-clock" style="color:yellow"></i>')
        elif value == "Failed":
            value = format_html('<i class="fa fa-exclamation-circle" style="color:red"></i>')
        return value

    class Meta:
        model = Collection
        exclude = ['celery_task_id_submission', 'celery_task_id_validation', 'user', 'modality','collection_type']
        template_name = 'django_tables2/bootstrap.html'

class CollectionRequestTable(tables.Table):
    """ The table used in the collection list. """

    # We use a collection's id as a link to the corresponding collection
    # detail.
    id = tables.LinkColumn(
        'ingest:collection_detail',
        verbose_name="",
        args=[A('pk')],
    # commenting out below line because i think it is interfering with template on ingest/template/submit_collection    
	text=format_html('<input type="checkbox" name = "submit_for_validation" id = "submit_for_validation" class="form-check-input"></checkbox>'))
        #text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        #attrs={'a': {'class': "btn btn-info", 'role': "button"}})
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

    def render_submission_status(self, value):
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

    def render_validation_status(self, value):
        """ Show the status as an icon. """
        if value == "Not submitted":
            value = format_html('<button type="button" class="btn btn-primary">Not Submitted</button>')
            #value = format_html('<i class="fa fa-minus" style="color:blue"></i>')
        elif value == "Success":
            value = format_html('<i class="fa fa-check" style="color:green"></i>')
        elif value == "Pending":
            value = format_html('<i class="fa fa-clock" style="color:yellow"></i>')
        elif value == "Failed":
            value = format_html('<i class="fa fa-exclamation-circle" style="color:red"></i>')
        return value

    class Meta:
        model = Collection
        exclude = ['celery_task_id_submission', 'celery_task_id_validation', 'user']
        template_name = 'ingest/bootstrap_ingest.html'

class ImageMetadataTable(tables.Table):
    """ The table used in the image metadata list. """

    # We use the metadata's id as a link to the corresponding collection
    # detail.
    id = tables.LinkColumn(
        'ingest:image_metadata_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<button type="button" class="btn btn-primary">Detail</button>')
        #text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        #attrs={'a': {'class': "btn btn-info", 'role': "button"}}
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
            'locked',
            'bil_uuid',
        ]

    # This gives us a checkbox for every piece of metadata, thereby allowing
    # the user to select and delete them (assuming they're unlocked).
    selection = tables.CheckBoxColumn(
        accessor="pk",
        attrs={"th__input": {"onclick": "toggle(this)"}},
        orderable=False)

class DescriptiveMetadataTable(tables.Table):
    """ The table used in the descriptive metadata list. """

    # We use the metadata's id as a link to the corresponding collection
    # detail.
    id = tables.LinkColumn(
        'ingest:descriptive_metadata_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html('<button type="button" class="btn btn-primary">Detail</button>')
        #text=format_html('<span class="glyphicon glyphicon-cog"></span>'),
        #attrs={'a': {'class': "btn btn-info", 'role': "button"}}
    )
    project_description = tables.Column()

    def render_locked(self, value):
        if value:
            value = format_html('<i class="fa fa-lock"></i>')
        else:
            value = format_html('<i class="fa fa-unlock"></i>')
        return value

    class Meta:
        model = DescriptiveMetadata
        template_name = 'ingest/bootstrap_ingest.html'
        # XXX: we should store this information in field_list
        exclude = [
        ]
        # the order of "sequence" determines the ordering of the columns
        sequence = [
            'id',
            'collection',
            'date_created',
            'last_edited',
            'locked',
            'sample_id', 
            'organism_type',
            'organism_ncbi_taxonomy_id', 
            'transgenetic_line_information', 
            'modality',
            'method',
            'technique',
            'anatomical_structure',
            'total_processed_cells',
            'organization',
            'lab',
            'investigator',
            'grant_number',
            'r24_name',
            'r24_directory',
        ]

    # This gives us a checkbox for every piece of metadata, thereby allowing
    # the user to select and delete them (assuming they're unlocked).
    selection = tables.CheckBoxColumn(
        accessor="pk",
        attrs={"th__input": {"onclick": "toggle(this)"}},
        orderable=False)
