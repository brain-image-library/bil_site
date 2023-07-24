from django.contrib import admin
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.html import format_html
from django.core import serializers
from django.http import HttpResponse
from django.contrib.admin import AdminSite
from django.utils.translation import ugettext_lazy
from django.http import HttpResponseRedirect
from django.db.models import F
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from ingest.forms import CollectionForm, AdminCollection
from django.db import models
from . import forms
from django import forms
from dal import autocomplete
from .models import ImageMetadata, Collection, People, Project, DescriptiveMetadata, Contributor, Instrument, Dataset, Specimen, Image, EventsLog, Sheet, ProjectPeople, Funder, Publication, Consortium, SWC

admin.site.site_header = 'Brain Image Library Admin Portal'
class ContributorsInline(admin.TabularInline):
    model = Contributor
class FundersInline(admin.TabularInline):
    model = Funder
class PublicationsInline(admin.TabularInline):
    model = Publication
class InstrumentsInline(admin.TabularInline):
    model = Instrument
class DatasetsInline(admin.TabularInline):
    model = Dataset
class SpecimensInline(admin.TabularInline):
    model = Specimen
class ImagesInline(admin.TabularInline):
    model = Image
class SWCSInline(admin.TabularInline):
    model = SWC
class ConsortiaInline(admin.TabularInline):
    model = Consortium
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
#@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    search_fields = ("bil_uuid__startswith", )
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

admin.site.register(Collection, CollectionAdmin)
admin.site.register(ImageMetadata)
@admin.register(People)
class PeopleAdmin(admin.ModelAdmin):
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
    autocomplete_fields = ["data_set", "specimen"]
    list_display = ("id", "microscopetype", "microscopemanufacturerandmodel", "objectivename", "objectiveimmersion", "objectivena", "objectivemagnification", "detectortype", "detectormodel", "illuminationtypes", "illuminationwavelength", "detectionwavelength", "sampletemperature", "sheet")
@admin.register(Dataset)
class Dataset(admin.ModelAdmin):
    search_fields = ("id__startswith", )
    list_display = ("id", "bildirectory", "socialmedia", "subject", "subjectscheme", "rights", "rightsuri", "rightsidentifier", "dataset_image", "generalmodality", "technique", "other", "methods", "technicalinfo", "sheet")
@admin.register(Specimen)
class Specimen(admin.ModelAdmin):
    search_fields = ("id__startswith", )
    list_display = ("id", "localid", "species", "ncbitaxonomy", "age", "ageunit", "sex", "genotype", "organlocalid", "organname", "samplelocalid", "atlas", "locations", "sheet", "data_set")
@admin.register(Image)
class Image(admin.ModelAdmin):
    list_display = ("id", "xaxis", "obliquexdim1", "obliquexdim2", "obliquexdim3", "yaxis", "obliqueydim1", "obliqueydim2", "obliqueydim3", "zaxis", "obliquezdim1", "obliquezdim2", "obliquezdim3", "landmarkname", "landmarkx", "landmarky", "landmarkz", "number", "displaycolor", "representation", "flurophore", "stepsizex", "stepsizey", "stepsizez", "stepsizet", "channels", "slices", "z", "xsize", "ysize", "zsize", "gbytes", "files", "dimensionorder", "sheet")
#@admin.register(Sheet)
class SheetAdmin(admin.ModelAdmin):
    #list_filter = ('collection__bil_uuid', 'bil_uuid',)
    search_fields = ('collection__bil_uuid', 'bil_uuid', )
    list_display = ("id","filename", "date_uploaded", "collection")
    inlines = [ContributorsInline, FundersInline, PublicationsInline, InstrumentsInline, SpecimensInline, DatasetsInline, ImagesInline, ]
admin.site.register(Sheet, SheetAdmin)

#@admin.register(EventsLog)
class EventsLogAdmin(admin.ModelAdmin):
    #form = AdminCollection
    autocomplete_fields = ["collection_id"]
    list_display = ("collection_id", "notes", "event_type","timestamp")
    list_filter = ('event_type','timestamp')
    def response_change(self, request, obj):
        """
        Override the default response after saving the model and redirect
        to the "add" page with pre-populated fields.
        """
        response = super().response_change(request, obj)

        if "_addanother" in request.POST:
            # Extract the object's foreign key values
            collection_id = obj.collection_id_id
            current_user=request.user
            people = get_object_or_404(People, auth_user_id=current_user.id)
            people_id = people.id
            project_id = obj.project_id_id

            # Build the URL for the "add" page with pre-populated fields
            redirect_url = f"/admin/ingest/eventslog/add/?collection_id={collection_id}&people_id={people_id}&project_id={project_id}"

            return redirect(redirect_url)

        return response
admin.site.register(EventsLog, EventsLogAdmin)
@admin.register(ProjectPeople)
class ProjectPeople(admin.ModelAdmin):
    list_display = ("id", "project_id", "people_id", "is_po", "is_po", "doi_role")
@admin.register(SWC)
class SWC(admin.ModelAdmin):
    list_display = ("id", "tracingFile", "sourceData", "sourceDataSample", "sourceDataSubmission", "coordinates", "coordinatesRegistration", "brainRegion", "brainRegionAtlas", "brainRegionAtlasName", "brainRegionAxonalProjection", "brainRegionDendriticProjection", "neuronType","segmentTags","proofreadingLevel", "notes", "sheet", "swc_uuid")
@admin.register(Consortium)
class Consortium(admin.ModelAdmin):
    list_display = ("id", "short_name", "long_name")
