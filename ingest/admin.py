import os
import mimetypes

from django.contrib import admin
from django.urls import path, reverse
from django.utils.http import urlencode
from django.utils.html import format_html
from django.core import serializers
from django.http import HttpResponse, FileResponse, Http404
from django.utils.translation import gettext_lazy
from django.db.models import F

from .models import (
    ImageMetadata, Collection, People, Project, DescriptiveMetadata, Contributor,
    Instrument, Dataset, Specimen, Image, EventsLog, Sheet, ProjectPeople, Funder,
    Publication, Consortium, SWC, DatasetLinkage, BIL_ID, ProjectConsortium, BIL_Specimen_ID, SpecimenLinkage, ConsortiumTag, DatasetTag, Spatial
)


admin.site.site_header = 'Brain Image Library Admin Portal'
class ContributorsInline(admin.TabularInline):
    model = Contributor
    show_change_link = True
    raw_id_fields = ('sheet',)

class FundersInline(admin.TabularInline):
    model = Funder
    show_change_link = True
    raw_id_fields = ('sheet',)

class PublicationsInline(admin.TabularInline):
    model = Publication
    show_change_link = True
    raw_id_fields = ('sheet','data_set',)

class InstrumentsInline(admin.TabularInline):
    model = Instrument
    show_change_link = True
    raw_id_fields = ('sheet','data_set','specimen',)

class DatasetsInline(admin.TabularInline):
    model = Dataset
    show_change_link = True
    raw_id_fields = ('sheet',)
    
class SpecimensInline(admin.TabularInline):
    model = Specimen
    show_change_link = True
    raw_id_fields = ('sheet','data_set',)

class ImagesInline(admin.TabularInline):
    model = Image
    show_change_link = True
    raw_id_fields = ('sheet','data_set', 'specimen',)

class SWCSInline(admin.TabularInline):
    model = SWC

class ConsortiaInline(admin.TabularInline):
    model = Consortium

@admin.register(ProjectConsortium)
class ProjectConsortiumAdmin(admin.ModelAdmin):
    list_display = [field.name for field in ProjectConsortium._meta.fields]
    search_fields = ['project__name', 'consortium__short_name']

class BIL_IDInline(admin.TabularInline):
    model = BIL_ID
    raw_id_fields = ('v2_ds_id',)

class BIL_Specimen_IDInline(admin.TabularInline):
    model = BIL_Specimen_ID

admin.site.disable_action('delete_selected')

@admin.action(description='Mark selected Collection(s) as Validated and Submitted')

def mark_as_validated_and_submitted(modeladmin, request, queryset):
    queryset.update(submission_status = 'SUCCESS', validation_status = 'SUCCESS')

@admin.action(description='Export results as JSON')

def export_as_json(modeladmin, request, queryset):
    coll_info = Collection.objects.filter(name = queryset)
    for i in coll_info:
        print(i)
    response = HttpResponse(content_type="application/json")
    serializers.serialize("json", queryset, stream=response)
    return response

@admin.register(Collection)

class CollectionAdmin(admin.ModelAdmin):
    search_fields = ("bil_uuid__startswith", "bil_uuid")
    list_display = ("bil_uuid","name","submission_status","validation_status", "view_descriptivemetadatas_link", "view_sheets_link","view_eventslogs_link")
    list_filter = ('submission_status', 'validation_status', 'lab_name', 'project', 'project_funder_id', 'user')
    actions = [mark_as_validated_and_submitted, export_as_json]
    ordering = ('bil_uuid',)
    def view_descriptivemetadatas_link(self, obj):
        count = obj.descriptivemetadata_set.count()
        url = (
            reverse("admin:ingest_descriptivemetadata_changelist")
            + "?"
            +urlencode({"collection__id": f"{obj.id}"})
        )
        return format_html('<a href="{}">{} Metadata Instances</a>', url, count)
    view_descriptivemetadatas_link.short_description = "MetadataV1(s)"
    def view_sheets_link(self, obj):
        count = obj.sheet_set.count()
        url = (
            reverse("admin:ingest_sheet_changelist")
            + "?"
            +urlencode({"collection__id": f"{obj.id}"})
        )
        return format_html('<a href="{}">{} Sheet Instances</a>', url, count)
    view_sheets_link.short_description = "MetadataV2(s)"
    def view_eventslogs_link(self, obj):
        count = obj.eventslog_set.count()
        url = (
            reverse("admin:ingest_eventslog_changelist")
            + "?"
            +urlencode({"collection_id": f"{obj.id}"})
        )
        return format_html('<a href="{}">{} Events</a>', url, count)
    view_eventslogs_link.short_description = "EventsLogs"

admin.site.register(ImageMetadata)

@admin.register(People)

class People(admin.ModelAdmin):
    list_display = ("id", "name", "orcid", "affiliation", "affiliation_identifier", "is_bil_admin", "auth_user_id")

@admin.register(Project)

class Project(admin.ModelAdmin):
    list_display = ("id", "name", "funded_by", "is_biccn")

@admin.register(DescriptiveMetadata)

class DescriptiveMetadataAdmin(admin.ModelAdmin):
    list_display = ("r24_directory", "investigator", "sample_id","collection")
    list_filter = ('investigator', 'lab')

@admin.register(Contributor)

class Contributor(admin.ModelAdmin):
    list_display = ("id", "contributorname", "creator", "contributortype", "nametype", "nameidentifier", "nameidentifierscheme", "affiliation", "affiliationidentifier", "affiliationidentifierscheme", "sheet")

@admin.register(Instrument)

class Instrument(admin.ModelAdmin):
    list_display = ("id", "microscopetype", "microscopemanufacturerandmodel", "objectivename", "objectiveimmersion", "objectivena", "objectivemagnification", "detectortype", "detectormodel", "illuminationtypes", "illuminationwavelength", "detectionwavelength", "sampletemperature", "sheet")

@admin.register(Dataset)

class Dataset(admin.ModelAdmin):
    search_fields = ['bildirectory']
    list_display = ("id", "bildirectory", "socialmedia", "subject", "subjectscheme", "rights", "rightsuri", "rightsidentifier", "dataset_image", "generalmodality", "technique", "other", "methods", "technicalinfo", "sheet")
    
@admin.register(Image)
class Image(admin.ModelAdmin):
    list_display = ("id", "xaxis", "obliquexdim1", "obliquexdim2", "obliquexdim3", "yaxis", "obliqueydim1", "obliqueydim2", "obliqueydim3", "zaxis", "obliquezdim1", "obliquezdim2", "obliquezdim3", "landmarkname", "landmarkx", "landmarky", "landmarkz", "number", "displaycolor", "representation", "flurophore", "stepsizex", "stepsizey", "stepsizez", "stepsizet", "channels", "slices", "z", "xsize", "ysize", "zsize", "gbytes", "files", "dimensionorder", "sheet")

class SpatialInline(admin.TabularInline):
    model = Spatial
    show_change_link = True
    raw_id_fields = ('sheet', 'data_set',)
@admin.register(Sheet)
class SheetAdmin(admin.ModelAdmin):
    list_display = ("id", "filename", "date_uploaded", "collection", "download_link")
    inlines = [ContributorsInline, FundersInline, PublicationsInline, InstrumentsInline, SpecimensInline, DatasetsInline, ImagesInline, SpatialInline]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:sheet_id>/download/",
                self.admin_site.admin_view(self.download_sheet),
                name="ingest_sheet_download",
            ),
        ]
        return custom + urls

    def download_sheet(self, request, sheet_id):
        try:
            sheet = Sheet.objects.get(pk=sheet_id)
        except Sheet.DoesNotExist:
            raise Http404
        filepath = sheet.filename
        if not os.path.isfile(filepath):
            raise Http404("File not found on disk.")
        mime_type, _ = mimetypes.guess_type(filepath)
        mime_type = mime_type or "application/octet-stream"
        response = FileResponse(open(filepath, "rb"), content_type=mime_type)
        response["Content-Disposition"] = f'attachment; filename="{os.path.basename(filepath)}"'
        return response

    def download_link(self, obj):
        url = reverse("admin:ingest_sheet_download", args=[obj.pk])
        return format_html('<a href="{}">Download</a>', url)
    download_link.short_description = "Download"

@admin.register(EventsLog)
class EventsLogAdmin(admin.ModelAdmin):
    list_display = ("collection_id", "notes", "event_type","timestamp")
    list_filter = ('event_type','timestamp')
    autocomplete_fields = ['collection_id']

@admin.register(ProjectPeople)

class ProjectPeople(admin.ModelAdmin):
    list_display = ("id", "project_id", "people_id", "is_pi", "is_po", "doi_role")

@admin.register(SWC)

class SWC(admin.ModelAdmin):
    list_display = ("id", "tracingFile", "sourceData", "sourceDataSample", "sourceDataSubmission", "coordinates", "coordinatesRegistration", "brainRegion", "brainRegionAtlas", "brainRegionAtlasName", "brainRegionAxonalProjection", "brainRegionDendriticProjection", "neuronType","segmentTags","proofreadingLevel", "notes", "sheet", "swc_uuid")

@admin.register(Consortium)

class Consortium(admin.ModelAdmin):
    list_display = ("id", "short_name", "long_name")

class DatasetLinkageAdmin(admin.ModelAdmin):
    list_display = ('data_id_1_bil', 'code_id', 'data_id_2', 'relationship', 'description', 'linkage_date')
    search_fields = ['data_id_1_bil__bil_id']  # Add the search field for autocomplete
    list_filter = ('code_id', 'relationship', 'linkage_date')
    autocomplete_fields = ['data_id_1_bil']

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
    list_display = ["bil_id", "v1_ds_id", "v2_ds_id", "r24_directory_display", "bildirectory_display", "metadata_version", "doi_status", "send_to_doi_button"]
    search_fields = ["bil_id"]
    list_filter = ["doi", DOIEligibleFilter]

    def r24_directory_display(self, obj):
        if not obj.v1_ds_id:
            return "-"
        val = obj.v1_ds_id.r24_directory or "-"
        return format_html(
            '<details><summary style="cursor:pointer;color:#447e9b;">View</summary>{}</details>',
            val,
        )
    r24_directory_display.short_description = "R24 Directory"

    def bildirectory_display(self, obj):
        if not obj.v2_ds_id:
            return "-"
        val = obj.v2_ds_id.bildirectory or "-"
        return format_html(
            '<details><summary style="cursor:pointer;color:#447e9b;">View</summary>{}</details>',
            val,
        )
    bildirectory_display.short_description = "BIL Directory"

    def doi_status(self, obj):
        ds = obj.v2_ds_id
        if not ds:
            return "(no v2 dataset)"
        return ds.doi or ""
    doi_status.short_description = "Dataset DOI"

    def _collection_ready_for_doi(self, ds) -> bool:
        """
        DOI can only be created if the dataset’s sheet->collection
        has submission_status=SUCCESS and validation_status=SUCCESS.
        """
        if not ds or not ds.sheet or not ds.sheet.collection:
            return False
        coll = ds.sheet.collection
        return coll.submission_status == "SUCCESS" and coll.validation_status == "SUCCESS"

    def send_to_doi_button(self, obj):
        ds = obj.v2_ds_id
        if not ds:
            return format_html('<span style="color:#999;">(no v2 dataset)</span>')

        # Already has a DOI string? show check
        if ds.doi:
            return format_html('<span style="color: green; font-weight: 600;">✅ DOI Created</span>')

        # Gate by collection status
        if not self._collection_ready_for_doi(ds):
            # You can hide it entirely OR show disabled w/ tooltip.
            # Disabled is nicer so admins understand why.
            coll = ds.sheet.collection if ds.sheet else None
            sub = getattr(coll, "submission_status", "UNKNOWN")
            val = getattr(coll, "validation_status", "UNKNOWN")

            return format_html(
                '<button type="button" class="button" disabled '
                'title="DOI can only be created when submission_status and validation_status are SUCCESS '
                '(currently: submission={}/validation={})">Create DOI</button>',
                sub, val
            )

        # Otherwise show enabled button
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

admin.site.register(DatasetLinkage, DatasetLinkageAdmin)

class Specimen_linkageAdmin(admin.ModelAdmin):
    list_display = ("specimen_id", "specimen_id_2", "code_id", "specimen_category")
    search_fields = ['specimen_id__bil_spc_id']
    autocomplete_fields = ['specimen_id']

class BIL_Specimen_IDAdmin(admin.ModelAdmin):
    search_fields = ['bil_spc_id']

admin.site.register(SpecimenLinkage, Specimen_linkageAdmin)

admin.site.register(BIL_Specimen_ID, BIL_Specimen_IDAdmin)

class SpecimenAdmin(admin.ModelAdmin):
    autocomplete_fields = ['data_set']

admin.site.register(Specimen, SpecimenAdmin)

#class ProjectConsortiumAdmin(admin.ModelAdmin):
    

admin.site.register(ConsortiumTag)

class DatasetTagAdmin(admin.ModelAdmin):
    list_display=["tag", "dataset", "bil_id"]


admin.site.register(DatasetTag, DatasetTagAdmin)

@admin.register(Spatial)
class SpatialAdmin(admin.ModelAdmin):
    # Adjust these to match your actual field names if needed
    list_display = ("id", "sheet", "data_set")
    search_fields = ("sheet__filename", "data_set__bildirectory")