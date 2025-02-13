from django.contrib import admin
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.html import format_html
from django.core import serializers
from django.http import HttpResponse
from django.utils.translation import gettext_lazy
from django.db.models import F
from django.urls import path
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from .views import doi_api  # Import the custom view

from .models import (
    ImageMetadata, Collection, People, Project, DescriptiveMetadata, Contributor,
    Instrument, Dataset, Specimen, Image, EventsLog, Sheet, ProjectPeople, Funder,
    Publication, Consortium, SWC, DatasetLinkage, BIL_ID, ProjectConsortium, BIL_Specimen_ID, SpecimenLinkage, ConsortiumTag, DatasetTag
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

class ProjectConsortiumInline(admin.TabularInline):
    model = ProjectConsortium

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

class DatasetAdmin(admin.ModelAdmin):
    search_fields = ['bildirectory']
    list_display = (
        "id", "bildirectory", "socialmedia", "subject", "subjectscheme",
        "rights", "rightsuri", "rightsidentifier", "dataset_image",
        "generalmodality", "technique", "other", "methods",
        "technicalinfo", "sheet"
    )

@admin.register(Image)
class Image(admin.ModelAdmin):
    list_display = ("id", "xaxis", "obliquexdim1", "obliquexdim2", "obliquexdim3", "yaxis", "obliqueydim1", "obliqueydim2", "obliqueydim3", "zaxis", "obliquezdim1", "obliquezdim2", "obliquezdim3", "landmarkname", "landmarkx", "landmarky", "landmarkz", "number", "displaycolor", "representation", "flurophore", "stepsizex", "stepsizey", "stepsizez", "stepsizet", "channels", "slices", "z", "xsize", "ysize", "zsize", "gbytes", "files", "dimensionorder", "sheet")

@admin.register(Sheet)
class SheetAdmin(admin.ModelAdmin):
    list_display = ("id","filename", "date_uploaded", "collection",)
    inlines = [ContributorsInline, FundersInline, PublicationsInline, InstrumentsInline, SpecimensInline, DatasetsInline, ImagesInline,]

@admin.register(EventsLog)
class EventsLogAdmin(admin.ModelAdmin):
    list_display = ("collection_id", "notes", "event_type","timestamp")
    list_filter = ('event_type','timestamp')
    autocomplete_fields = ['collection_id']

@admin.register(ProjectPeople)

class ProjectPeople(admin.ModelAdmin):
    list_display = ("id", "project_id", "people_id", "is_po", "is_po", "doi_role")

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

class BIL_IDAdmin(admin.ModelAdmin):
    list_display = ["bil_id", "v1_ds_id", "v2_ds_id", "metadata_version", "doi", "send_to_doi_button"]
    search_fields = ['bil_id']

    def send_to_doi_button(self, obj):
        """Button that sends the BIL_ID to the DOI API via AJAX and opens the DOI page"""

        # If DOI is already created, do NOT show the button
        if obj.doi:
            return format_html('<span style="color: green; font-weight: bold;">✅ DOI Created</span>')

        doi_api_url = reverse("ingest:doi_api")  # Ensure this is the correct URL name

        return format_html(
            '''
            <button type="button" onclick="sendBILID('{bil_id}', '{doi_api_url}')">
                Create DOI
            </button>

            <script>
                function sendBILID(bil_id, url) {{
                    event.stopPropagation();  // Prevents row click behavior
                    event.preventDefault();  // Prevents form submission

                    if (!confirm("Are you sure you want to send this BIL_ID?")) {{
                        return;
                    }}

                    console.log('📤 Sending BIL_ID:', bil_id); 

                    const payload = {{
                        "bildid": bil_id,
                        "action": "draft"
                    }};
                    console.log('📦 Payload:', payload);

                    fetch(url, {{
                        method: "POST",
                        headers: {{
                            "Content-Type": "application/json",
                            "X-CSRFToken": getCSRFToken()
                        }},
                        body: JSON.stringify(payload)
                    }})
                    .then(response => response.json())
                    .then(data => {{
                        if (data.success && data.doi_url) {{
                            alert("✅ DOI successfully created!");
                            setTimeout(() => {{
                                window.open(data.doi_url, "_blank");  // 🚀 Open DOI page in new tab
                                location.reload();  // 🔄 Refresh the page after DOI is created
                            }}, 500);
                        }} else {{
                            alert("❌ Error: " + (data.error || "Unknown error"));
                        }}
                    }})
                    .catch(error => {{
                        console.error('❌ Error:', error);
                        alert("❌ Failed to communicate with the server.");
                    }});
                }}

                function getCSRFToken() {{
                    return document.cookie.split('; ')
                        .find(row => row.startsWith('csrftoken='))
                        ?.split('=')[1] || '';
                }}
            </script>
            ''',
            bil_id=obj.bil_id, doi_api_url=doi_api_url
        )

    send_to_doi_button.short_description = "Create DOI"


    #send_to_doi_button.short_description = "Send to DOI API"
admin.site.register(BIL_ID, BIL_IDAdmin)

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


admin.site.register(ProjectConsortium)
    

admin.site.register(ConsortiumTag)

class DatasetTagAdmin(admin.ModelAdmin):
    list_display=["tag", "dataset", "bil_id"]


admin.site.register(DatasetTag, DatasetTagAdmin)

#class CustomAdminSite(admin.AdminSite):
#    site_header = "Custom Admin"

#    def get_urls(self):
#        urls = super().get_urls()
#        custom_urls = [
#            path('trigger-script/', self.admin_view(trigger_bash_script), name='trigger_bash_script'),
#        ]
#        return custom_urls + urls
#
#    def custom_button_view(self):
#        url = reverse('admin:trigger_bash_script')
#        return format_html('<a class="button" href="{}">Run Bash Script</a>', url)

# Instantiate the custom admin site
#custom_admin_site = CustomAdminSite(name='custom_admin')
