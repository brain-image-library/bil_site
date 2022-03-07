from django.contrib import admin
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.html import format_html

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

#admin.site.register(Collection)
admin.site.disable_action('delete_selected')
@admin.action(description='Mark selected Collection(s) as Validated and Submitted')
def mark_as_validated_and_submitted(modeladmin, request, queryset):
    queryset.update(submission_status = 'SUCCESS', validation_status = 'SUCCESS')
@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    search_fields = ("bil_uuid__startswith", )
    list_display = ("bil_uuid","name","submission_status","validation_status", "view_descriptivemetadatas_link")
    actions = [mark_as_validated_and_submitted]
    def view_descriptivemetadatas_link(self, obj):
        count = obj.descriptivemetadata_set.count()
        url = (
            reverse("admin:ingest_descriptivemetadata_changelist")
            + "?"
            +urlencode({"collection__id": f"{obj.id}"})
        )
        return format_html('<a href="{}">{} Metadata Instances</a>', url, count)
    view_descriptivemetadatas_link.short_description = "DescriptiveMetadatas"
admin.site.register(ImageMetadata)
admin.site.register(People)
admin.site.register(Project)
#admin.site.register(DescriptiveMetadata)
@admin.register(DescriptiveMetadata)
class DescriptiveMetadataAdmin(admin.ModelAdmin):
    list_display = ("r24_directory", "sample_id","collection")
admin.site.register(Contributor)
admin.site.register(Instrument)
admin.site.register(Dataset)
admin.site.register(Specimen)
admin.site.register(Image)
#admin.site.register(EventsLog) #collection_id, notes, timestamp
@admin.register(EventsLog)
class EventsLogAdmin(admin.ModelAdmin):
    list_display = ("collection_id", "notes", "event_type","timestamp")
