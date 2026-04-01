from django.contrib import admin
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.html import format_html
from django.core import serializers
from django.http import HttpResponse
from django.utils.translation import gettext_lazy
from django.db.models import F

from .models import (
    ImageMetadata, Collection, People, Project, DescriptiveMetadata, Contributor,
    Instrument, Dataset, Specimen, Image, EventsLog, Sheet, ProjectPeople, Funder,
    Publication, Consortium, SWC, DatasetLinkage, BIL_ID, ProjectConsortium,
    BIL_Specimen_ID, SpecimenLinkage, ConsortiumTag, DatasetTag, Spatial,
    DatasetEventsLog, MetadataVersion, ProjectAssociation, DataGroup,
    BIL_Instrument_ID, BIL_Project_ID,
)


admin.site.site_header = 'Brain Image Library Admin Portal'
admin.site.disable_action('delete_selected')


# ---------------------------------------------------------------------------
# Inline classes
# ---------------------------------------------------------------------------

class ContributorsInline(admin.TabularInline):
    model = Contributor
    show_change_link = True
    raw_id_fields = ('sheet',)
    extra = 0

class FundersInline(admin.TabularInline):
    model = Funder
    show_change_link = True
    raw_id_fields = ('sheet',)
    extra = 0

class PublicationsInline(admin.TabularInline):
    model = Publication
    show_change_link = True
    raw_id_fields = ('sheet', 'data_set',)
    extra = 0

class InstrumentsInline(admin.TabularInline):
    model = Instrument
    show_change_link = True
    raw_id_fields = ('sheet', 'data_set', 'specimen',)
    extra = 0

class DatasetsInline(admin.TabularInline):
    model = Dataset
    show_change_link = True
    raw_id_fields = ('sheet',)
    extra = 0
    readonly_fields = ('bil_id_link',)
    fields = ('bil_id_link', 'bildirectory', 'title', 'doi', 'generalmodality', 'technique', 'sheet')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('v2_ds_id')

    def bil_id_link(self, obj):
        bil = obj.v2_ds_id.first()
        if not bil:
            return '—'
        url = reverse("admin:ingest_bil_id_change", args=[bil.id])
        return format_html('<a href="{}" style="white-space:nowrap">{}</a>', url, bil.bil_id)
    bil_id_link.short_description = "BIL ID"

class SpecimensInline(admin.TabularInline):
    model = Specimen
    show_change_link = True
    raw_id_fields = ('sheet', 'data_set',)
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('data_set', 'sheet')

class ImagesInline(admin.TabularInline):
    model = Image
    show_change_link = True
    raw_id_fields = ('sheet', 'data_set', 'specimen',)
    extra = 0
    classes = ('collapse',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('data_set', 'specimen', 'sheet')

class SWCSInline(admin.TabularInline):
    model = SWC
    extra = 0
    classes = ('collapse',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('data_set', 'sheet')

class ConsortiaInline(admin.TabularInline):
    model = Consortium
    extra = 0

class ProjectConsortiumInline(admin.TabularInline):
    model = ProjectConsortium
    show_change_link = True
    extra = 0

class SpatialInline(admin.TabularInline):
    model = Spatial
    show_change_link = True
    raw_id_fields = ('sheet', 'data_set',)
    extra = 0
    classes = ('collapse',)

class BIL_IDInline(admin.TabularInline):
    model = BIL_ID
    raw_id_fields = ('v2_ds_id',)
    extra = 0

class BIL_Specimen_IDInline(admin.TabularInline):
    model = BIL_Specimen_ID
    extra = 0


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@admin.action(description='Mark selected Collection(s) as Validated and Submitted')
def mark_as_validated_and_submitted(modeladmin, request, queryset):
    queryset.update(submission_status='SUCCESS', validation_status='SUCCESS')


@admin.action(description='Export selected as JSON')
def export_as_json(modeladmin, request, queryset):
    response = HttpResponse(content_type="application/json")
    serializers.serialize("json", queryset, stream=response)
    return response


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    search_fields = ('bil_uuid', 'name', 'user__username', 'lab_name', 'organization_name')
    list_display = (
        'bil_uuid', 'name', 'submission_status', 'validation_status', 'locked',
        'user', 'lab_name', 'view_descriptivemetadatas_link', 'view_sheets_link',
        'view_eventslogs_link',
    )
    list_filter = ('submission_status', 'validation_status', 'locked', 'lab_name', 'project', 'project_funder_id', 'user')
    readonly_fields = ('bil_uuid', 'data_path', 'celery_task_id_submission', 'celery_task_id_validation')
    actions = [mark_as_validated_and_submitted, export_as_json]
    ordering = ('bil_uuid',)
    list_select_related = ('user', 'project')

    def view_descriptivemetadatas_link(self, obj):
        count = obj.descriptivemetadata_set.count()
        url = (
            reverse("admin:ingest_descriptivemetadata_changelist")
            + "?" + urlencode({"collection__id": f"{obj.id}"})
        )
        return format_html('<a href="{}">{} Metadata Instances</a>', url, count)
    view_descriptivemetadatas_link.short_description = "MetadataV1(s)"

    def view_sheets_link(self, obj):
        count = obj.sheet_set.count()
        url = (
            reverse("admin:ingest_sheet_changelist")
            + "?" + urlencode({"collection__id": f"{obj.id}"})
        )
        return format_html('<a href="{}">{} Sheet Instances</a>', url, count)
    view_sheets_link.short_description = "MetadataV2(s)"

    def view_eventslogs_link(self, obj):
        count = obj.eventslog_set.count()
        url = (
            reverse("admin:ingest_eventslog_changelist")
            + "?" + urlencode({"collection_id": f"{obj.id}"})
        )
        return format_html('<a href="{}">{} Events</a>', url, count)
    view_eventslogs_link.short_description = "EventsLogs"


# ---------------------------------------------------------------------------
# Sheet
# ---------------------------------------------------------------------------

@admin.register(Sheet)
class SheetAdmin(admin.ModelAdmin):
    list_display = ('id', 'filename', 'date_uploaded', 'collection',)
    search_fields = ('filename', 'collection__name', 'collection__bil_uuid')
    inlines = [
        ContributorsInline, FundersInline, PublicationsInline,
        InstrumentsInline, SpecimensInline, DatasetsInline,
        ImagesInline, SpatialInline, SWCSInline,
    ]


# ---------------------------------------------------------------------------
# People / Project
# ---------------------------------------------------------------------------

@admin.register(People)
class PeopleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'orcid', 'affiliation', 'affiliation_identifier', 'is_bil_admin', 'auth_user_id')
    search_fields = ('name', 'orcid', 'affiliation')
    list_filter = ('is_bil_admin',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'funded_by', 'is_biccn')
    search_fields = ('name', 'funded_by')
    list_filter = ('is_biccn', 'funded_by')
    inlines = [ProjectConsortiumInline]


@admin.register(ProjectPeople)
class ProjectPeopleAdmin(admin.ModelAdmin):
    list_display = ('id', 'project_id', 'people_id', 'is_pi', 'is_po', 'doi_role')
    search_fields = ('project_id__name', 'people_id__name')
    list_filter = ('is_pi', 'is_po')


@admin.register(ProjectConsortium)
class ProjectConsortiumAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ProjectConsortium._meta.fields]
    search_fields = ['project__name', 'consortium__short_name']


@admin.register(ProjectAssociation)
class ProjectAssociationAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'parent_project')
    search_fields = ('project__name', 'parent_project__name')


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

admin.site.register(ImageMetadata)


@admin.register(DescriptiveMetadata)
class DescriptiveMetadataAdmin(admin.ModelAdmin):
    list_display = ('r24_directory', 'investigator', 'sample_id', 'collection', 'date_created', 'last_edited')
    list_filter = ('investigator', 'lab')
    search_fields = ('sample_id', 'r24_directory', 'investigator', 'collection__name')
    readonly_fields = ('date_created', 'last_edited')


@admin.register(MetadataVersion)
class MetadataVersionAdmin(admin.ModelAdmin):
    list_display = ('id', 'dataset_id_ds', 'metadata_version', 'dataset_doi', 'dataset_status', 'event')
    list_filter = ('metadata_version', 'dataset_status')
    search_fields = ('dataset_doi', 'dataset_id_ds__bildirectory')


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    search_fields = ('bildirectory', 'title', 'doi')
    list_display = (
        'id', 'bildirectory', 'title', 'doi', 'generalmodality', 'technique',
        'dataset_size', 'number_of_files', 'sheet',
    )
    list_filter = ('generalmodality', 'technique', 'rights')


@admin.register(DataGroup)
class DataGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_group_list_id', 'dm_id')


# ---------------------------------------------------------------------------
# Contributor / Funder / Publication
# ---------------------------------------------------------------------------

@admin.register(Contributor)
class ContributorAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'contributorname', 'creator', 'contributortype', 'nametype',
        'nameidentifier', 'nameidentifierscheme', 'affiliation',
        'affiliationidentifier', 'affiliationidentifierscheme', 'sheet',
    )
    search_fields = ('contributorname', 'affiliation')


# ---------------------------------------------------------------------------
# Instrument / Image / SWC / Spatial / Specimen
# ---------------------------------------------------------------------------

@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'microscopetype', 'microscopemanufacturerandmodel', 'objectivename',
        'objectiveimmersion', 'objectivena', 'objectivemagnification', 'detectortype',
        'detectormodel', 'illuminationtypes', 'illuminationwavelength',
        'detectionwavelength', 'sampletemperature', 'sheet',
    )
    search_fields = ('microscopetype', 'microscopemanufacturerandmodel')


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'xaxis', 'obliquexdim1', 'obliquexdim2', 'obliquexdim3',
        'yaxis', 'obliqueydim1', 'obliqueydim2', 'obliqueydim3',
        'zaxis', 'obliquezdim1', 'obliquezdim2', 'obliquezdim3',
        'landmarkname', 'landmarkx', 'landmarky', 'landmarkz',
        'number', 'displaycolor', 'representation', 'flurophore',
        'stepsizex', 'stepsizey', 'stepsizez', 'stepsizet',
        'channels', 'slices', 'z', 'xsize', 'ysize', 'zsize',
        'gbytes', 'files', 'dimensionorder', 'sheet',
    )


@admin.register(SWC)
class SWCAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'tracingFile', 'sourceData', 'sourceDataSample', 'sourceDataSubmission',
        'coordinates', 'coordinatesRegistration', 'brainRegion', 'brainRegionAtlas',
        'brainRegionAtlasName', 'brainRegionAxonalProjection', 'brainRegionDendriticProjection',
        'neuronType', 'segmentTags', 'proofreadingLevel', 'notes', 'sheet', 'swc_uuid',
    )
    search_fields = ('swc_uuid', 'brainRegion', 'neuronType')


@admin.register(Spatial)
class SpatialAdmin(admin.ModelAdmin):
    list_display = ('id', 'sheet', 'data_set')
    search_fields = ('sheet__filename', 'data_set__bildirectory')


@admin.register(Specimen)
class SpecimenAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'localid', 'species', 'ncbitaxonomy', 'age', 'ageunit', 'sex',
        'genotype', 'organlocalid', 'organname', 'samplelocalid', 'atlas',
        'locations', 'data_set', 'sheet',
    )
    search_fields = ('species', 'localid', 'samplelocalid', 'ncbitaxonomy')
    list_filter = ('species', 'sex', 'ageunit')
    autocomplete_fields = ['data_set']


# ---------------------------------------------------------------------------
# Events logs
# ---------------------------------------------------------------------------

@admin.register(EventsLog)
class EventsLogAdmin(admin.ModelAdmin):
    list_display = ('collection_id', 'people_id', 'project_id', 'event_type', 'notes', 'timestamp')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('collection_id__name', 'collection_id__bil_uuid', 'notes')
    autocomplete_fields = ['collection_id']


@admin.register(DatasetEventsLog)
class DatasetEventsLogAdmin(admin.ModelAdmin):
    list_display = ('dataset_id', 'collection_id', 'project_id', 'event_type', 'notes', 'timestamp')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('dataset_id__bildirectory', 'collection_id__name', 'notes')


# ---------------------------------------------------------------------------
# Consortium / Tags
# ---------------------------------------------------------------------------

@admin.register(Consortium)
class ConsortiumAdmin(admin.ModelAdmin):
    list_display = ('id', 'short_name', 'long_name')
    search_fields = ('short_name', 'long_name')


admin.site.register(ConsortiumTag)


@admin.register(DatasetTag)
class DatasetTagAdmin(admin.ModelAdmin):
    list_display = ('tag', 'dataset', 'bil_id')
    search_fields = ('tag__tag', 'dataset__bildirectory')


# ---------------------------------------------------------------------------
# BIL IDs / Linkages
# ---------------------------------------------------------------------------

class DOIEligibleFilter(admin.SimpleListFilter):
    title = "DOI Eligible"
    parameter_name = "doi_eligible"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Ready for DOI"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                doi=False,
                v2_ds_id__sheet__collection__submission_status=Collection.SUCCESS,
                v2_ds_id__sheet__collection__validation_status=Collection.SUCCESS,
            )
        return queryset


@admin.register(BIL_ID)
class BIL_IDAdmin(admin.ModelAdmin):
    list_display = ('bil_id', 'v1_ds_id', 'v2_ds_id', 'collection_name', 'metadata_version', 'doi_status', 'send_to_doi_button')
    search_fields = ('bil_id',)
    list_filter = ('doi', DOIEligibleFilter)
    list_select_related = ('v2_ds_id', 'v1_ds_id')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('v2_ds_id__sheet__collection')

    def collection_name(self, obj):
        ds = obj.v2_ds_id
        if not ds or not ds.sheet or not ds.sheet.collection:
            return '—'
        coll = ds.sheet.collection
        url = reverse("admin:ingest_collection_change", args=[coll.id])
        return format_html('<a href="{}">{}</a>', url, coll.name)
    collection_name.short_description = "Collection"

    def doi_status(self, obj):
        ds = obj.v2_ds_id
        if not ds:
            return "(no v2 dataset)"
        return ds.doi or ""
    doi_status.short_description = "Dataset DOI"

    def _collection_ready_for_doi(self, ds) -> bool:
        if not ds or not ds.sheet or not ds.sheet.collection:
            return False
        coll = ds.sheet.collection
        return coll.submission_status == "SUCCESS" and coll.validation_status == "SUCCESS"

    def send_to_doi_button(self, obj):
        ds = obj.v2_ds_id
        if not ds:
            return format_html('<span style="color:#999;">(no v2 dataset)</span>')

        if ds.doi:
            return format_html('<span style="color: green; font-weight: 600;">✅ DOI Created</span>')

        if not self._collection_ready_for_doi(ds):
            coll = ds.sheet.collection if ds.sheet else None
            sub = getattr(coll, "submission_status", "UNKNOWN")
            val = getattr(coll, "validation_status", "UNKNOWN")
            return format_html(
                '<button type="button" class="button" disabled '
                'title="DOI can only be created when submission_status and validation_status are SUCCESS '
                '(currently: submission={}/validation={})">Create DOI</button>',
                sub, val
            )

        doi_api_url = reverse("ingest:doi_api")
        return format_html(
            '<button type="button" class="button bil-doi-btn" '
            'data-bil-id="{}" data-url="{}">Create DOI</button>',
            obj.bil_id,
            doi_api_url,
        )
    send_to_doi_button.short_description = "Create DOI"

    class Media:
        js = ("ingest/admin/doi_button.js",)


@admin.register(BIL_Specimen_ID)
class BIL_Specimen_IDAdmin(admin.ModelAdmin):
    search_fields = ('bil_spc_id',)
    list_display = ('id', 'bil_spc_id', 'specimen_id', 'specimen_species', 'specimen_dataset')
    list_select_related = ('specimen_id',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('specimen_id__data_set')

    def specimen_species(self, obj):
        if obj.specimen_id:
            return obj.specimen_id.species
        return '—'
    specimen_species.short_description = "Species"

    def specimen_dataset(self, obj):
        if obj.specimen_id and obj.specimen_id.data_set:
            ds = obj.specimen_id.data_set
            url = reverse("admin:ingest_dataset_change", args=[ds.id])
            return format_html('<a href="{}">{}</a>', url, ds.bildirectory)
        return '—'
    specimen_dataset.short_description = "Dataset"


@admin.register(BIL_Instrument_ID)
class BIL_Instrument_IDAdmin(admin.ModelAdmin):
    list_display = ('id', 'bil_ins_id', 'instrument_id')
    search_fields = ('bil_ins_id',)


@admin.register(BIL_Project_ID)
class BIL_Project_IDAdmin(admin.ModelAdmin):
    list_display = ('id', 'bil_prj_id', 'project_id')
    search_fields = ('bil_prj_id', 'project_id__name')


@admin.register(DatasetLinkage)
class DatasetLinkageAdmin(admin.ModelAdmin):
    list_display = ('data_id_1_bil', 'code_id', 'data_id_2', 'relationship', 'description', 'linkage_date')
    search_fields = ('data_id_1_bil__bil_id',)
    list_filter = ('code_id', 'relationship', 'linkage_date')
    autocomplete_fields = ('data_id_1_bil',)


@admin.register(SpecimenLinkage)
class SpecimenLinkageAdmin(admin.ModelAdmin):
    list_display = ('specimen_id', 'specimen_id_2', 'code_id', 'specimen_category')
    search_fields = ('specimen_id__bil_spc_id',)
    autocomplete_fields = ('specimen_id',)
