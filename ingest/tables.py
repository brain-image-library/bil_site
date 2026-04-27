from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Collection
from .models import ImageMetadata
from .models import DescriptiveMetadata
from .models import Sheet, Project, ProjectConsortium, Specimen, BIL_Specimen_ID, SpecimenLinkage, EventsLog
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

    id = tables.LinkColumn(
        'ingest:collection_detail',
        verbose_name="",
        args=[A('pk')],
        text=format_html(
            '<button type="button" class="btn btn-sm" '
            'style="background-color:#161b33;color:#fff;border-color:#161b33;">'
            '<i class="fa-solid fa-arrow-right me-1"></i>Open'
            '</button>'
        ),
    )

    description = tables.Column()

    # Status/icon columns — centred header + cell
    submission_status = tables.Column(
        verbose_name="Sub. Status",
        attrs={
            'th': {'class': 'text-center text-nowrap'},
            'td': {'class': 'text-center'},
        },
    )
    validation_status = tables.Column(
        verbose_name="Val. Status",
        attrs={
            'th': {'class': 'text-center text-nowrap'},
            'td': {'class': 'text-center'},
        },
    )
    locked = tables.Column(
        attrs={
            'th': {'class': 'text-center'},
            'td': {'class': 'text-center'},
        },
    )

    # Shorter header labels for the detail columns
    lab_name  = tables.Column(verbose_name="Lab")
    data_path = tables.Column(verbose_name="Data Path")

    bican_ids_button = tables.Column(
        verbose_name="Actions",
        accessor='pk',
        orderable=False,
        empty_values=(),
    )

    def render_bican_ids_button(self, record):
        most_recent_sheet = Sheet.objects.filter(collection_id=record.id).last()
        if most_recent_sheet:
            if record.submission_status == 'SUCCESS':
                return mark_safe(
                    '<span class="badge text-bg-success px-2 py-1">'
                    '<i class="fa-solid fa-globe me-1"></i>Data Public</span>'
                )
            elif record.submission_status == 'PENDING':
                return mark_safe(
                    '<span class="badge text-bg-warning px-2 py-1">'
                    '<i class="fa-solid fa-clock me-1"></i>Validation Requested</span>'
                )
            elif record.submission_status == 'FAILED':
                return mark_safe(
                    '<a href="{}" class="btn btn-sm btn-outline-secondary">'
                    '<i class="fa-solid fa-rotate-right me-1"></i>Retry Publication</a>'.format(
                        reverse('ingest:submit_request_collection_list')
                    )
                )
            elif ProjectConsortium.objects.filter(project=record.project, consortium__short_name='BICAN').exists():
                specimens = Specimen.objects.filter(sheet=most_recent_sheet)
                bil_specimen_ids = BIL_Specimen_ID.objects.filter(specimen_id__in=specimens)
                if SpecimenLinkage.objects.filter(specimen_id__in=bil_specimen_ids).exists():
                    already_requested = EventsLog.objects.filter(
                        collection_id=record.id,
                        event_type='request_validation',
                    ).exists()
                    if already_requested:
                        return mark_safe(
                            '<span class="badge text-bg-warning px-2 py-1">'
                            '<i class="fa-solid fa-clock me-1"></i>Validation Requested</span>'
                        )
                    return mark_safe(
                        '<a href="{}" class="btn btn-sm btn-outline-secondary">'
                        '<i class="fa-solid fa-paper-plane me-1"></i>Request Publication</a>'.format(
                            reverse('ingest:submit_request_collection_list')
                        )
                    )
                else:
                    return mark_safe(
                        '<a href="{}" class="btn btn-sm" style="background-color:#161b33;color:#fff;border-color:#161b33;">'
                        '<i class="fa-solid fa-id-card me-1"></i>Add BICAN IDs</a>'.format(
                            reverse('ingest:bican_id_upload', args=[most_recent_sheet.pk])
                        )
                    )
            else:
                already_requested = EventsLog.objects.filter(
                    collection_id=record.id,
                    event_type='request_validation',
                ).exists()
                if already_requested:
                    return mark_safe(
                        '<span class="badge text-bg-warning px-2 py-1">'
                        '<i class="fa-solid fa-clock me-1"></i>Validation Requested</span>'
                    )
                return mark_safe(
                    '<a href="{}" class="btn btn-sm btn-outline-secondary">'
                    '<i class="fa-solid fa-paper-plane me-1"></i>Request Publication</a>'.format(
                        reverse('ingest:submit_request_collection_list')
                    )
                )
        return mark_safe(
            '<a href="{}" class="btn btn-sm btn-warning">'
            '<i class="fa-solid fa-triangle-exclamation me-1"></i>Needs Metadata</a>'.format(
                reverse('ingest:descriptive_metadata_upload', args=[record.id])
            )
        )

    @staticmethod
    def _truncate(value, limit):
        s = str(value)
        if len(s) <= limit:
            return s
        return format_html(
            '<span data-bs-toggle="tooltip" data-bs-placement="top"'
            ' data-bs-custom-class="tooltip-wide" title="{}">{}</span>',
            s, s[:limit] + '…'
        )

    def render_name(self, value):
        return self._truncate(value, 30)

    def render_description(self, value):
        return self._truncate(value, 40)

    def render_lab_name(self, value):
        return self._truncate(value, 24)

    def render_data_path(self, value):
        return self._truncate(value, 30)

    def render_locked(self, value):
        if value:
            return format_html(
                '<span class="badge text-bg-secondary">'
                '<i class="fa-solid fa-lock me-1"></i>Locked</span>'
            )
        return format_html(
            '<span class="badge border text-muted">'
            '<i class="fa-solid fa-lock-open me-1"></i>Open</span>'
        )

    def render_submission_status(self, value):
        if value == "Not submitted":
            return format_html(
                '<span class="badge text-bg-secondary">'
                '<i class="fa-solid fa-minus me-1"></i>Not Submitted</span>'
            )
        elif value == "Success":
            return format_html(
                '<span class="badge text-bg-success">'
                '<i class="fa-solid fa-check me-1"></i>Success</span>'
            )
        elif value == "Pending":
            return format_html(
                '<span class="badge text-bg-warning">'
                '<i class="fa-solid fa-clock me-1"></i>Pending</span>'
            )
        elif value == "Failed":
            return format_html(
                '<span class="badge text-bg-danger">'
                '<i class="fa-solid fa-circle-exclamation me-1"></i>Failed</span>'
            )
        return value

    def render_validation_status(self, value):
        if value == "Not validated":
            return format_html(
                '<span class="badge text-bg-secondary">'
                '<i class="fa-solid fa-minus me-1"></i>Not Validated</span>'
            )
        elif value == "Success":
            return format_html(
                '<span class="badge text-bg-success">'
                '<i class="fa-solid fa-check me-1"></i>Valid</span>'
            )
        elif value == "Pending":
            return format_html(
                '<span class="badge text-bg-warning">'
                '<i class="fa-solid fa-clock me-1"></i>Pending</span>'
            )
        elif value == "Failed":
            return format_html(
                '<span class="badge text-bg-danger">'
                '<i class="fa-solid fa-circle-exclamation me-1"></i>Failed</span>'
            )
        return value

    class Meta:
        model = Collection
        exclude = [
            'celery_task_id_submission', 'celery_task_id_validation', 'user',
            'modality', 'collection_type',
            'organization_name', 'project_funder_id', 'project_funder', 'bil_uuid',
        ]
        template_name = 'ingest/collection_table.html'
        sequence = [
            'id', 'name', 'description', 'submission_status', 'validation_status',
            'locked', 'lab_name', 'data_path', 'project', 'bican_ids_button',
        ]
        attrs = {'class': 'table table-sm table-hover table-col-constrain'}

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
