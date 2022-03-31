from django.contrib import admin
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.html import format_html
from django.core import serializers
from django.http import HttpResponse

from .models import ImageMetadata
from .models import Collection
from .models import People
from .models import Project
from .models import DescriptiveMetadata
from .models import Contributor
from .models import Instrument
from .models import Dataset
from .models import Specimen
from .models import Image
from .models import EventsLog
from .models import Sheet 

#admin.site.register(Collection)
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
    search_fields = ("bil_uuid__startswith", )
    list_display = ("bil_uuid","name","submission_status","validation_status", "view_descriptivemetadatas_link", "view_sheets_link","view_eventslogs_link")
    list_filter = ('submission_status', 'validation_status', 'lab_name', 'project')
    actions = [mark_as_validated_and_submitted, export_as_json]
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
        contributors = []
        count = obj.sheet_set.count()
        sheets = Sheet.objects.filter(collection_id = obj.id).all()
        for s in sheets:
            contrib = Contributor.objects.filter(sheet_id = s.id).all()
            contributors.append(contrib)
        url = (
            reverse("admin:ingest_sheet_changelist")
            + "?"
            +urlencode({"collection__id": f"{obj.id}"})
        )
        return format_html('<a href="{}">{} Sheet Instances</a>', url, count, contributors)
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
admin.site.register(People)
admin.site.register(Project)
#admin.site.register(DescriptiveMetadata)
@admin.register(DescriptiveMetadata)
class DescriptiveMetadataAdmin(admin.ModelAdmin):
    list_display = ("r24_directory", "sample_id","collection")
#admin.site.register(Contributor)
@admin.register(Contributor)
class Contributor(admin.ModelAdmin):
    list_display = ("contributorname", "creator", "contributortype", "nametype", "nameidentifier", "nameidentifierscheme", "affiliation", "affiliationidentifier", "affiliationidentifierscheme", "sheet")
admin.site.register(Instrument)
admin.site.register(Dataset)
admin.site.register(Specimen)
admin.site.register(Image)
#admin.site.register(Sheet)
@admin.register(Sheet)
class SheetAdmin(admin.ModelAdmin):
    list_display = ("filename", "date_uploaded", "collection")
#admin.site.register(EventsLog) #collection_id, notes, timestamp
@admin.register(EventsLog)
class EventsLogAdmin(admin.ModelAdmin):
    list_display = ("collection_id", "notes", "event_type","timestamp")
