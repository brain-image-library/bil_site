import os
import re
import shutil
import mimetypes
import tempfile

from django.contrib import admin
from django.urls import path, reverse
from django.utils.http import urlencode
from django.utils.html import format_html
from django.core import serializers
from django.db.models import OuterRef, Subquery
from django.http import HttpResponse, FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.contrib import messages
from django.forms import modelformset_factory, HiddenInput, Textarea
from unfold.admin import ModelAdmin as UnfoldModelAdmin, TabularInline as UnfoldTabularInline
from unfold.contrib.filters.admin import ChoicesDropdownFilter
from unfold.decorators import action as unfold_action

from .models import (
    ImageMetadata, Collection, People, Project, DescriptiveMetadata, Contributor,
    Instrument, Dataset, Specimen, Image, EventsLog, Sheet, ProjectPeople, Funder,
    Publication, Consortium, SWC, DatasetLinkage, BIL_ID, ProjectConsortium,
    BIL_Specimen_ID, SpecimenLinkage, ConsortiumTag, DatasetTag, Spatial,
)

admin.site.site_header = 'Brain Image Library Admin Portal'
admin.site.disable_action('delete_selected')


# ── Inlines ───────────────────────────────────────────────────────────────────

class ContributorsInline(UnfoldTabularInline):
    model = Contributor
    show_change_link = True
    extra = 0
    autocomplete_fields = ('sheet',)

class FundersInline(UnfoldTabularInline):
    model = Funder
    show_change_link = True
    extra = 0
    autocomplete_fields = ('sheet',)

class PublicationsInline(UnfoldTabularInline):
    model = Publication
    show_change_link = True
    extra = 0
    autocomplete_fields = ('sheet', 'data_set')

class InstrumentsInline(UnfoldTabularInline):
    model = Instrument
    show_change_link = True
    extra = 0
    classes = ['collapse']
    autocomplete_fields = ('sheet', 'data_set', 'specimen')

class DatasetsInline(UnfoldTabularInline):
    model = Dataset
    show_change_link = True
    extra = 0
    autocomplete_fields = ('sheet',)

class SpecimensInline(UnfoldTabularInline):
    model = Specimen
    show_change_link = True
    extra = 0
    autocomplete_fields = ('sheet', 'data_set')

class ImagesInline(UnfoldTabularInline):
    model = Image
    show_change_link = True
    extra = 0
    classes = ['collapse']
    fields = ('number', 'channels', 'xsize', 'ysize', 'zsize', 'gbytes', 'data_set', 'specimen')
    autocomplete_fields = ('data_set', 'specimen')

class SWCSInline(UnfoldTabularInline):
    model = SWC
    show_change_link = True
    extra = 0
    classes = ['collapse']
    autocomplete_fields = ('sheet', 'data_set')

class ProjectConsortiumInline(UnfoldTabularInline):
    model = ProjectConsortium
    extra = 0
    autocomplete_fields = ('project', 'consortium')

class BIL_IDInline(UnfoldTabularInline):
    model = BIL_ID
    extra = 0
    autocomplete_fields = ('v2_ds_id',)

class BIL_Specimen_IDInline(UnfoldTabularInline):
    model = BIL_Specimen_ID
    extra = 0
    autocomplete_fields = ('specimen_id',)

class SpatialInline(UnfoldTabularInline):
    model = Spatial
    show_change_link = True
    extra = 0
    classes = ['collapse']
    autocomplete_fields = ('sheet', 'data_set')


class SheetInline(UnfoldTabularInline):
    model = Sheet
    extra = 0
    classes = ['collapse']
    show_change_link = False
    fields = ('filename', 'date_uploaded', 'edit_link')
    readonly_fields = ('filename', 'date_uploaded', 'edit_link')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="")
    def edit_link(self, obj):
        url = reverse('admin:ingest_sheet_change', args=[obj.pk])
        return format_html('<a href="{}">Edit →</a>', url)


# ── Actions ───────────────────────────────────────────────────────────────────

@admin.action(description='Mark selected Collection(s) as public (SUCCESS/SUCCESS/locked)')
def mark_as_validated_and_submitted(modeladmin, request, queryset):
    queryset.update(submission_status='SUCCESS', validation_status='SUCCESS', locked=True)
    now = timezone.now()
    EventsLog.objects.bulk_create([
        EventsLog(
            collection_id=collection,
            notes='Marked public by BIL admin',
            timestamp=now,
            event_type='collection_public',
        )
        for collection in queryset
    ])

@admin.action(description='Export results as JSON')
def export_as_json(modeladmin, request, queryset):
    response = HttpResponse(content_type="application/json")
    serializers.serialize("json", queryset, stream=response)
    return response


# ── Custom list filters ───────────────────────────────────────────────────────

class ConsortiumFilter(admin.SimpleListFilter):
    title = 'Consortium'
    parameter_name = 'consortium'

    def lookups(self, request, model_admin):
        qs = Consortium.objects.filter(
            projectconsortium__project__collection__isnull=False
        ).distinct().order_by('short_name')
        return [(c.pk, c.short_name) for c in qs]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                project__projectconsortium__consortium_id=self.value()
            ).distinct()
        return queryset


class CollectionEventTypeFilter(admin.SimpleListFilter):
    title = 'Event type'
    parameter_name = 'event_type'

    def lookups(self, request, model_admin):
        return EventsLog._meta.get_field('event_type').choices

    def queryset(self, request, queryset):
        if self.value():
            # Matches collections that have *any* event of this type, not only the latest.
            return queryset.filter(eventslog__event_type=self.value()).distinct()
        return queryset


class PublicStatusFilter(admin.SimpleListFilter):
    title = 'Public status'
    parameter_name = 'public_status'

    def lookups(self, request, model_admin):
        return (
            ('public', 'Public'),
            ('in_progress', 'In Progress (Not Public)'),
            ('awaiting_validation', 'Awaiting Validation'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'public':
            return queryset.filter(submission_status=Collection.SUCCESS)
        if self.value() == 'in_progress':
            return queryset.exclude(submission_status=Collection.SUCCESS)
        if self.value() == 'awaiting_validation':
            latest_event = EventsLog.objects.filter(
                collection_id=OuterRef('pk')
            ).order_by('-timestamp').values('event_type')[:1]
            return queryset.exclude(
                submission_status=Collection.SUCCESS
            ).annotate(
                latest_event_type=Subquery(latest_event)
            ).filter(latest_event_type='request_validation')
        return queryset


# ── V2 update helpers ─────────────────────────────────────────────────────────

def _v2_cleanup(tmp_dir):
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass


def _v2_parse_errors(xls_path, error_map):
    """Return a list of dicts describing each validation error with editable metadata."""
    import xlrd
    wb = xlrd.open_workbook(xls_path)
    details = []
    for key in sorted(error_map.keys()):
        messages = error_map[key]
        sheet_name, row_str, col_str = key.split('::')
        row, col = int(row_str), int(col_str)
        try:
            ws = wb.sheet_by_name(sheet_name)
            current_value = str(ws.cell_value(row, col))
        except Exception:
            current_value = ''
        msg = messages[0]
        field_name = ''
        choices = []
        m = re.match(r'"([^"]+)" invalid value.*?must be one of: (.+)', msg)
        if m:
            field_name = m.group(1)
            choices = [c.strip() for c in m.group(2).split(',')]
        else:
            m = re.match(r'"([^"]+)" is required', msg)
            if m:
                field_name = m.group(1)
            else:
                m = re.match(r'(\w+) must begin with', msg)
                if m:
                    field_name = m.group(1)
        details.append({
            'key': key,
            'input_name': f'override__{sheet_name}__{row}__{col}',
            'sheet': sheet_name,
            'display_row': row + 1,
            'field_name': field_name or f'{sheet_name} col {col + 1}',
            'current_value': current_value,
            'messages': messages,
            'choices': choices,
        })
    return details


def _v2_success_response(request, context, collection):
    from ingest.services.v2_verifier import check_directory_match, get_bil_id_summary
    match_results = check_directory_match(collection)
    bil_summary = get_bil_id_summary(collection)
    try:
        owner_people = People.objects.get(auth_user_id=collection.user)
    except People.DoesNotExist:
        owner_people = None
    EventsLog.objects.create(
        collection_id=collection,
        people_id=owner_people,
        project_id=collection.project,
        notes='Updated to V2 via admin portal',
        event_type='updated_to_v2',
        timestamp=timezone.now(),
    )
    context.update({
        'step': '3_success',
        'match_results': match_results,
        'bil_summary': bil_summary,
    })
    return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)


# ── Model Admins ──────────────────────────────────────────────────────────────

@admin.register(Collection)
class CollectionAdmin(UnfoldModelAdmin):
    fieldsets = (
        ("Overview", {
            "fields": ("name", "description", "organization_name", "lab_name"),
            "classes": ["tab"],
        }),
        ("Project & Funding", {
            "fields": ("project", "project_funder", "project_funder_id", "modality", "collection_type"),
            "classes": ["tab"],
        }),
        ("Status & Access", {
            "fields": ("submission_status", "validation_status", "locked", "user"),
            "classes": ["tab"],
        }),
        ("Technical", {
            "fields": ("bil_uuid", "data_path", "celery_task_id_submission", "celery_task_id_validation"),
            "classes": ["tab"],
        }),
    )
    show_facets = admin.ShowFacets.ALWAYS
    search_fields = ("bil_uuid", "name")
    search_help_text = "Search by BIL UUID"
    list_display = (
        "bil_uuid", "name", "submission_status", "validation_status",
        "locked", "user",
        "view_datasets_link", "view_bil_ids_link",
        "view_descriptivemetadatas_link",
        "view_sheets_link", "view_eventslogs_link",
    )
    list_filter = [
        ("submission_status", ChoicesDropdownFilter),
        ("validation_status", ChoicesDropdownFilter),
        PublicStatusFilter,
        ConsortiumFilter,
        CollectionEventTypeFilter,
    ]
    list_select_related = ['project', 'user']
    autocomplete_fields = ['project', 'user']
    actions = [mark_as_validated_and_submitted, export_as_json]
    ordering = ('bil_uuid',)
    actions_detail = ("mark_as_public",)
    inlines = [SheetInline]

    class Media:
        css = {
            'all': ['ingest/admin/collection_datasets.css'],
        }

    DATASET_EDITABLE_FIELDS = [
        'bildirectory', 'title', 'doi', 'generalmodality', 'technique',
        'abstract', 'methods', 'rights', 'rightsuri', 'rightsidentifier',
        'subject', 'subjectscheme', 'dataset_size', 'number_of_files', 'sheet',
    ]

    def _dataset_formset_factory(self):
        return modelformset_factory(
            Dataset,
            fields=self.DATASET_EDITABLE_FIELDS,
            extra=0,
            widgets={
                'sheet': HiddenInput(),
                'abstract': Textarea(attrs={'rows': 3, 'cols': 30}),
                'methods': Textarea(attrs={'rows': 3, 'cols': 30}),
            },
        )

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if extra_context is None:
            extra_context = {}
        if object_id:
            extra_context['v2_update_url'] = reverse(
                'admin:ingest_collection_v2_update', args=[object_id]
            )
        if object_id and request.method == 'GET':
            try:
                collection = Collection.objects.get(pk=object_id)
            except Collection.DoesNotExist:
                return super().changeform_view(request, object_id, form_url, extra_context)
            latest_sheet = Sheet.objects.filter(collection=collection).order_by('-date_uploaded').first()
            qs = (
                Dataset.objects.filter(sheet=latest_sheet).prefetch_related('v2_ds_id')
                if latest_sheet else Dataset.objects.none()
            )
            extra_context['dataset_formset'] = self._dataset_formset_factory()(queryset=qs)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/datasets/save/',
                self.admin_site.admin_view(self.save_datasets),
                name='ingest_collection_save_datasets',
            ),
            path(
                '<int:pk>/v2-update/',
                self.admin_site.admin_view(self.v2_update_view),
                name='ingest_collection_v2_update',
            ),
        ]
        return custom_urls + urls

    def save_datasets(self, request, pk):
        if request.method != 'POST':
            return HttpResponseRedirect(reverse('admin:ingest_collection_change', args=[pk]))
        latest_sheet = Sheet.objects.filter(collection_id=pk).order_by('-date_uploaded').first()
        qs = Dataset.objects.filter(sheet=latest_sheet) if latest_sheet else Dataset.objects.none()
        allowed_pks = set(qs.values_list('pk', flat=True))
        formset = self._dataset_formset_factory()(request.POST, queryset=qs)
        if formset.is_valid():
            for form in formset:
                if form.instance.pk and form.instance.pk not in allowed_pks:
                    messages.error(request, 'Unauthorized: submitted dataset does not belong to this collection.')
                    return HttpResponseRedirect(reverse('admin:ingest_collection_change', args=[pk]))
            formset.save()
            messages.success(request, 'Datasets saved.')
        else:
            errors = '; '.join(
                f"{field}: {', '.join(str(e) for e in errs)}"
                for form in formset
                for field, errs in form.errors.items()
            )
            messages.error(request, f'Dataset save failed: {errors}')
        return HttpResponseRedirect(reverse('admin:ingest_collection_change', args=[pk]))

    def v2_update_view(self, request, pk):
        from ingest.services.v2_validator import run_preflight, validate_spreadsheet
        from ingest.services.upload_service import execute_v2_upload

        collection = get_object_or_404(Collection, pk=pk)
        context = {
            **self.admin_site.each_context(request),
            'collection': collection,
            'title': f'V2 Update — {collection.name}',
            'opts': Collection._meta,
            'has_view_permission': True,
        }

        step = request.POST.get('step', '1') if request.method == 'POST' else '1'

        if step == 'unlock':
            collection.locked = False
            collection.save()
            return HttpResponseRedirect(reverse('admin:ingest_collection_v2_update', args=[pk]))

        if request.method == 'GET' or step == '1':
            preflight_errors = run_preflight(collection)
            if preflight_errors:
                context['preflight_errors'] = preflight_errors
                context['collection_locked'] = collection.locked
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)

            try:
                from ingest.services.drive_service import search_by_uuid
                files = search_by_uuid(collection.bil_uuid)
                context['drive_error'] = None
            except Exception as e:
                files = []
                context['drive_error'] = str(e)

            context['files'] = files
            context['step'] = '1'
            return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)

        elif step == '2':
            file_id = request.POST.get('file_id', '').strip()
            file_name = request.POST.get('file_name', '').strip()
            if not file_id:
                return HttpResponseRedirect(
                    reverse('admin:ingest_collection_v2_update', args=[pk])
                )

            tmp_dir = tempfile.mkdtemp()
            tmp_ext = os.path.splitext(file_id)[1] or '.xls'
            tmp_path = os.path.join(tmp_dir, f'{collection.bil_uuid}{tmp_ext}')
            try:
                from ingest.services.drive_service import download_file
                download_file(file_id, tmp_path)
                errors, warnings = validate_spreadsheet(tmp_path)
            except Exception as e:
                context['download_error'] = str(e)
                context['step'] = '2'
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)
            finally:
                try:
                    os.remove(tmp_path)
                    os.rmdir(tmp_dir)
                except Exception:
                    pass

            ingest_method_choices = [
                ('ingest_1', 'Method 1 — Light Sheet / Confocal (with Image sheet)'),
                ('ingest_2', 'Method 2 — Electron Microscopy (with Image sheet)'),
                ('ingest_3', 'Method 3 — MRI / Other volume (no Image sheet)'),
                ('ingest_4', 'Method 4 — Multimodal'),
                ('ingest_5', 'Method 5 — SWC / Morphology (with SWC sheet, no Image sheet)'),
                ('ingest_6', 'Method 6 — Spatial Transcriptomics'),
            ]
            context.update({
                'step': '2',
                'file_id': file_id,
                'file_name': file_name,
                'validation_errors': errors,
                'validation_warnings': warnings,
                'ingest_method_choices': ingest_method_choices,
            })
            return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)

        elif step == '3':
            file_id = request.POST.get('file_id', '').strip()
            ingest_method = request.POST.get('ingest_method', 'ingest_1')

            tmp_dir = tempfile.mkdtemp()
            tmp_ext = os.path.splitext(file_id)[1] or '.xls'
            tmp_path = os.path.join(tmp_dir, f'{collection.bil_uuid}{tmp_ext}')

            try:
                from ingest.services.drive_service import download_file
                download_file(file_id, tmp_path)
            except Exception as e:
                _v2_cleanup(tmp_dir)
                context.update({'upload_error': str(e), 'step': '3_failed'})
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)

            if tmp_path.endswith('.xlsx'):
                from ingest.services.upload_service import _convert_xlsx_to_xls
                xls_path = _convert_xlsx_to_xls(tmp_path)
            else:
                xls_path = tmp_path

            from ingest.views import check_all_sheets
            error_map = check_all_sheets(xls_path, ingest_method, collection_data_path=collection.data_path)
            if error_map:
                request.session['v2_fixup_tmp_dir'] = tmp_dir
                request.session['v2_fixup_xls_path'] = xls_path
                request.session['v2_fixup_file_id'] = file_id
                context.update({
                    'step': '3_fixup',
                    'error_details': _v2_parse_errors(xls_path, error_map),
                    'ingest_method': ingest_method,
                    'file_name': os.path.basename(file_id),
                })
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)

            try:
                success, error_msg, _ = execute_v2_upload(
                    xls_path, collection, collection.user, ingest_method
                )
            except Exception as e:
                context.update({'upload_error': str(e), 'step': '3_failed'})
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)
            finally:
                _v2_cleanup(tmp_dir)

            if not success:
                context.update({'upload_error': error_msg, 'step': '3_failed'})
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)

            return _v2_success_response(request, context, collection)

        elif step == '3_retry':
            ingest_method = request.POST.get('ingest_method', 'ingest_1')
            tmp_dir = request.session.get('v2_fixup_tmp_dir')
            xls_path = request.session.get('v2_fixup_xls_path')
            file_id = request.session.get('v2_fixup_file_id', '')

            if not xls_path or not os.path.exists(xls_path):
                context.update({'upload_error': 'Editing session expired — please start over.', 'step': '3_failed'})
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)

            overrides = {}
            for k, v in request.POST.items():
                if k.startswith('override__'):
                    parts = k.split('__')
                    if len(parts) == 4:
                        _, sheet_name, row_str, col_str = parts
                        try:
                            overrides[(sheet_name, int(row_str), int(col_str))] = v
                        except ValueError:
                            pass

            if overrides:
                from ingest.services.upload_service import _apply_xls_overrides
                _apply_xls_overrides(xls_path, overrides)

            from ingest.views import check_all_sheets
            error_map = check_all_sheets(xls_path, ingest_method, collection_data_path=collection.data_path)
            if error_map:
                context.update({
                    'step': '3_fixup',
                    'error_details': _v2_parse_errors(xls_path, error_map),
                    'ingest_method': ingest_method,
                    'file_name': os.path.basename(file_id),
                })
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)

            try:
                success, error_msg, _ = execute_v2_upload(
                    xls_path, collection, collection.user, ingest_method
                )
            except Exception as e:
                context.update({'upload_error': str(e), 'step': '3_failed'})
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)
            finally:
                if tmp_dir:
                    _v2_cleanup(tmp_dir)
                for k in ('v2_fixup_tmp_dir', 'v2_fixup_xls_path', 'v2_fixup_file_id'):
                    request.session.pop(k, None)

            if not success:
                context.update({'upload_error': error_msg, 'step': '3_failed'})
                return TemplateResponse(request, 'admin/ingest/collection/v2_update.html', context)

            return _v2_success_response(request, context, collection)

        return HttpResponseRedirect(reverse('admin:ingest_collection_v2_update', args=[pk]))

    @unfold_action(description="Mark as Validated/Public")
    def mark_as_public(self, request, object_id):
        collection = Collection.objects.get(pk=object_id)
        if (
            collection.submission_status == Collection.SUCCESS
            and collection.validation_status == Collection.SUCCESS
        ):
            self.message_user(
                request, "Collection is already marked as public.", messages.WARNING
            )
        else:
            collection.submission_status = Collection.SUCCESS
            collection.validation_status = Collection.SUCCESS
            collection.locked = True
            collection.save()
            EventsLog.objects.create(
                collection_id=collection,
                notes='Marked public by BIL admin',
                event_type='collection_public',
                timestamp=timezone.now(),
            )
            self.message_user(
                request, "Collection marked as validated/public.", messages.SUCCESS
            )
        return HttpResponseRedirect(
            reverse("admin:ingest_collection_change", args=[object_id])
        )

    @admin.display(description="Datasets")
    def view_datasets_link(self, obj):
        count = Dataset.objects.filter(sheet__collection=obj).count()
        url = reverse("admin:ingest_dataset_changelist") + "?" + urlencode({"sheet__collection__id": obj.id})
        return format_html('<a href="{}">{} Dataset(s)</a>', url, count)

    @admin.display(description="BIL IDs")
    def view_bil_ids_link(self, obj):
        count = BIL_ID.objects.filter(v2_ds_id__sheet__collection=obj).count()
        url = reverse("admin:ingest_bil_id_changelist") + "?" + urlencode({"v2_ds_id__sheet__collection__id": obj.id})
        return format_html('<a href="{}">{} BIL ID(s)</a>', url, count)

    @admin.display(description="MetadataV1(s)")
    def view_descriptivemetadatas_link(self, obj):
        count = obj.descriptivemetadata_set.count()
        url = reverse("admin:ingest_descriptivemetadata_changelist") + "?" + urlencode({"collection__id": obj.id})
        return format_html('<a href="{}">{} Metadata Instances</a>', url, count)

    @admin.display(description="MetadataV2(s)")
    def view_sheets_link(self, obj):
        count = obj.sheet_set.count()
        url = reverse("admin:ingest_sheet_changelist") + "?" + urlencode({"collection__id": obj.id})
        return format_html('<a href="{}">{} Sheet Instances</a>', url, count)

    @admin.display(description="EventsLogs")
    def view_eventslogs_link(self, obj):
        count = obj.eventslog_set.count()
        url = reverse("admin:ingest_eventslog_changelist") + "?" + urlencode({"collection_id": obj.id})
        return format_html('<a href="{}">{} Events</a>', url, count)


@admin.register(ImageMetadata)
class ImageMetadataAdmin(UnfoldModelAdmin):
    pass


@admin.register(People)
class PeopleAdmin(UnfoldModelAdmin):
    list_display = ("id", "name", "orcid", "affiliation", "affiliation_identifier", "is_bil_admin", "auth_user_id")
    search_fields = ('name', 'orcid')
    list_select_related = ['auth_user_id']


@admin.register(Project)
class ProjectAdmin(UnfoldModelAdmin):
    list_display = ("id", "name", "funded_by", "is_biccn", "is_brain_initiative")
    search_fields = ('name',)
    inlines = [ProjectConsortiumInline]


@admin.register(DescriptiveMetadata)
class DescriptiveMetadataAdmin(UnfoldModelAdmin):
    show_facets = admin.ShowFacets.ALWAYS
    list_display = ("r24_directory", "investigator", "sample_id", "collection")
    list_filter = ('investigator', 'lab')
    search_fields = ('r24_directory', 'investigator')
    autocomplete_fields = ['collection']


@admin.register(Contributor)
class ContributorAdmin(UnfoldModelAdmin):
    list_display = ("id", "contributorname", "creator", "contributortype", "nametype",
                    "nameidentifier", "nameidentifierscheme", "affiliation",
                    "affiliationidentifier", "affiliationidentifierscheme", "sheet")
    list_select_related = ['sheet']
    search_fields = ('contributorname',)
    autocomplete_fields = ['sheet']


@admin.register(Instrument)
class InstrumentAdmin(UnfoldModelAdmin):
    list_display = ("id", "microscopetype", "microscopemanufacturerandmodel", "objectivename",
                    "objectiveimmersion", "objectivena", "objectivemagnification", "detectortype",
                    "detectormodel", "illuminationtypes", "illuminationwavelength",
                    "detectionwavelength", "sampletemperature", "sheet")
    list_select_related = ['sheet', 'data_set']
    autocomplete_fields = ['sheet', 'data_set']


@admin.register(Dataset)
class DatasetAdmin(UnfoldModelAdmin):
    fieldsets = (
        ("Identity & Description", {
            "fields": (
                "bildirectory", "sheet", "title", "abstract",
                "doi", "generalmodality", "technique", "other", "socialmedia",
            ),
            "classes": ["tab"],
        }),
        ("Rights & Metrics", {
            "fields": (
                "rights", "rightsuri", "rightsidentifier",
                "subject", "subjectscheme", "dataset_image",
                "methods", "technicalinfo",
                "dataset_size", "number_of_files",
                "specimen_ingest_method_4",
            ),
            "classes": ["tab"],
        }),
    )
    search_fields = ['bildirectory', 'sheet__collection__name']
    list_display = (
        "bildirectory", "collection_link", "sheet_link",
        "title", "doi", "generalmodality", "technique",
        "subject", "rights", "dataset_size", "number_of_files",
        "view_linkages_link",
    )

    list_select_related = ['sheet__collection']
    list_per_page = 25
    autocomplete_fields = ['sheet']
    inlines = [BIL_IDInline, SWCSInline]

    def lookup_allowed(self, lookup, value, request=None):
        if lookup == 'sheet__collection__id':
            return True
        return super().lookup_allowed(lookup, value, request)

    @admin.display(description="Collection")
    def collection_link(self, obj):
        if not obj.sheet or not obj.sheet.collection:
            return "-"
        coll = obj.sheet.collection
        url = reverse("admin:ingest_collection_change", args=[coll.id])
        return format_html('<a href="{}">{}</a>', url, coll.name)

    @admin.display(description="Sheet")
    def sheet_link(self, obj):
        if not obj.sheet:
            return "-"
        url = reverse("admin:ingest_sheet_change", args=[obj.sheet.id])
        return format_html('<a href="{}">{}</a>', url, obj.sheet.filename)

    @admin.display(description="Linkages")
    def view_linkages_link(self, obj):
        count = DatasetLinkage.objects.filter(data_id_1_bil__v2_ds_id=obj).count()
        if not count:
            return '-'
        url = (
            reverse("admin:ingest_datasetlinkage_changelist")
            + "?" + urlencode({"data_id_1_bil__v2_ds_id__id": obj.id})
        )
        return format_html('<a href="{}">{} Linkage(s)</a>', url, count)


@admin.register(Image)
class ImageAdmin(UnfoldModelAdmin):
    list_display = ("id", "xaxis", "obliquexdim1", "obliquexdim2", "obliquexdim3", "yaxis",
                    "obliqueydim1", "obliqueydim2", "obliqueydim3", "zaxis", "obliquezdim1",
                    "obliquezdim2", "obliquezdim3", "landmarkname", "landmarkx", "landmarky",
                    "landmarkz", "number", "displaycolor", "representation", "flurophore",
                    "stepsizex", "stepsizey", "stepsizez", "stepsizet", "channels", "slices",
                    "z", "xsize", "ysize", "zsize", "gbytes", "files", "dimensionorder", "sheet")
    list_select_related = ['sheet', 'data_set', 'specimen']
    autocomplete_fields = ['sheet', 'data_set', 'specimen']


@admin.register(Sheet)
class SheetAdmin(UnfoldModelAdmin):
    list_display = ("id", "filename", "collection", "date_uploaded", "download_link")
    list_select_related = ['collection']
    search_fields = ['filename', 'collection__name']
    inlines = [ContributorsInline, FundersInline, PublicationsInline, InstrumentsInline,
               SpecimensInline, DatasetsInline, ImagesInline, SWCSInline, SpatialInline]

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

    @admin.display(description="Download")
    def download_link(self, obj):
        url = reverse("admin:ingest_sheet_download", args=[obj.pk])
        return format_html('<a href="{}">Download</a>', url)


@admin.register(EventsLog)
class EventsLogAdmin(UnfoldModelAdmin):
    show_facets = admin.ShowFacets.ALWAYS
    list_display = ("collection_id", "notes", "event_type", "timestamp")
    list_filter = [
        ("event_type", ChoicesDropdownFilter),
        "timestamp",
    ]
    date_hierarchy = 'timestamp'
    list_select_related = ['collection_id', 'people_id']
    autocomplete_fields = ['collection_id', 'people_id', 'project_id']


@admin.register(ProjectPeople)
class ProjectPeopleAdmin(UnfoldModelAdmin):
    list_display = ("id", "project_id", "people_id", "is_pi", "is_po", "doi_role")
    list_select_related = ['project_id', 'people_id']
    search_fields = ('project_id__name', 'people_id__name')
    autocomplete_fields = ['project_id', 'people_id']


@admin.register(SWC)
class SWCAdmin(UnfoldModelAdmin):
    list_display = ("id", "tracingFile", "sourceData", "sourceDataSample", "sourceDataSubmission",
                    "coordinates", "coordinatesRegistration", "brainRegion", "brainRegionAtlas",
                    "brainRegionAtlasName", "brainRegionAxonalProjection",
                    "brainRegionDendriticProjection", "neuronType", "segmentTags",
                    "proofreadingLevel", "notes", "sheet", "swc_uuid")
    list_select_related = ['sheet', 'data_set']
    autocomplete_fields = ['sheet', 'data_set']


@admin.register(Consortium)
class ConsortiumAdmin(UnfoldModelAdmin):
    list_display = ("id", "short_name", "long_name")
    search_fields = ('short_name', 'long_name')


@admin.register(ProjectConsortium)
class ProjectConsortiumAdmin(UnfoldModelAdmin):
    list_display = [field.name for field in ProjectConsortium._meta.fields]
    list_select_related = ['project', 'consortium']
    search_fields = ['project__name', 'consortium__short_name']
    autocomplete_fields = ['project', 'consortium']


class DOIEligibleFilter(admin.SimpleListFilter):
    title = "DOI Eligible"
    parameter_name = "doi_eligible"

    def lookups(self, request, model_admin):
        return (("yes", "Ready for DOI"),)

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                doi=False,
                v2_ds_id__sheet__collection__submission_status=Collection.SUCCESS,
                v2_ds_id__sheet__collection__validation_status=Collection.SUCCESS,
            )
        return queryset


@admin.register(BIL_ID)
class BIL_IDAdmin(UnfoldModelAdmin):
    show_facets = admin.ShowFacets.ALWAYS
    list_display = ["bil_id", "v1_ds_id", "v2_ds_id", "r24_directory_display",
                    "bildirectory_display", "metadata_version", "doi_status", "send_to_doi_button"]
    search_fields = ["bil_id"]
    search_help_text = "Search by BIL ID"
    list_filter = ["doi", DOIEligibleFilter]
    autocomplete_fields = ['v1_ds_id', 'v2_ds_id']

    def lookup_allowed(self, lookup, value, request=None):
        if lookup == 'v2_ds_id__sheet__collection__id':
            return True
        return super().lookup_allowed(lookup, value, request)

    @admin.display(description="R24 Directory")
    def r24_directory_display(self, obj):
        if not obj.v1_ds_id:
            return "-"
        val = obj.v1_ds_id.r24_directory or "-"
        return format_html(
            '<details class="bil-dir-details">'
            '<summary class="bil-dir-summary">View</summary>'
            '<div class="bil-dir-popover">{}</div>'
            '</details>',
            val,
        )

    @admin.display(description="BIL Directory")
    def bildirectory_display(self, obj):
        if not obj.v2_ds_id:
            return "-"
        val = obj.v2_ds_id.bildirectory or "-"
        return format_html(
            '<details class="bil-dir-details">'
            '<summary class="bil-dir-summary">View</summary>'
            '<div class="bil-dir-popover">{}</div>'
            '</details>',
            val,
        )

    @admin.display(description="Dataset DOI")
    def doi_status(self, obj):
        ds = obj.v2_ds_id
        if not ds:
            return "(no v2 dataset)"
        return ds.doi or ""

    def _collection_ready_for_doi(self, ds) -> bool:
        if not ds or not ds.sheet or not ds.sheet.collection:
            return False
        coll = ds.sheet.collection
        return coll.submission_status == "SUCCESS" and coll.validation_status == "SUCCESS"

    @admin.display(description="Create DOI")
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
                sub, val,
            )

        doi_api_url = reverse("ingest:doi_api")
        return format_html(
            '<button type="button" class="button bil-doi-btn" '
            'data-bil-id="{}" data-url="{}">Create DOI</button>',
            obj.bil_id,
            doi_api_url,
        )

    class Media:
        js = ("ingest/admin/doi_button.js",)


@admin.register(DatasetLinkage)
class DatasetLinkageAdmin(UnfoldModelAdmin):
    show_facets = admin.ShowFacets.ALWAYS
    list_display = ('data_id_1_bil', 'code_id', 'data_id_2', 'relationship', 'description', 'linkage_date')
    search_fields = ['data_id_1_bil__bil_id']
    list_filter = ('code_id', 'relationship', 'linkage_date')
    list_select_related = ['data_id_1_bil']
    autocomplete_fields = ['data_id_1_bil']

    def lookup_allowed(self, lookup, value, request=None):
        if lookup == 'data_id_1_bil__v2_ds_id__id':
            return True
        return super().lookup_allowed(lookup, value, request)


@admin.register(SpecimenLinkage)
class SpecimenLinkageAdmin(UnfoldModelAdmin):
    list_display = ("specimen_id", "specimen_id_2", "code_id", "specimen_category")
    search_fields = ['specimen_id__bil_spc_id']
    list_select_related = ['specimen_id']
    autocomplete_fields = ['specimen_id']


@admin.register(BIL_Specimen_ID)
class BIL_Specimen_IDAdmin(UnfoldModelAdmin):
    list_display = ('bil_spc_id', 'specimen_id')
    list_select_related = ['specimen_id']
    search_fields = ['bil_spc_id']
    autocomplete_fields = ['specimen_id']


@admin.register(Specimen)
class SpecimenAdmin(UnfoldModelAdmin):
    list_display = ('id', 'localid', 'species', 'sex', 'organname', 'samplelocalid', 'sheet', 'data_set')
    search_fields = ('localid', 'species', 'samplelocalid')
    list_filter = ('species', 'sex')
    list_select_related = ['sheet', 'data_set']
    autocomplete_fields = ['data_set']
    inlines = [BIL_Specimen_IDInline]


@admin.register(ConsortiumTag)
class ConsortiumTagAdmin(UnfoldModelAdmin):
    list_display = ('tag', 'consortium')
    list_select_related = ['consortium']
    list_filter = ('consortium',)
    search_fields = ('tag', 'consortium__short_name')


@admin.register(DatasetTag)
class DatasetTagAdmin(UnfoldModelAdmin):
    list_display = ["tag", "dataset", "bil_id"]
    list_select_related = ['tag', 'dataset', 'bil_id']
    autocomplete_fields = ['tag', 'dataset', 'bil_id']


@admin.register(Spatial)
class SpatialAdmin(UnfoldModelAdmin):
    list_display = ("id", "sheet", "data_set")
    search_fields = ("sheet__filename", "data_set__bildirectory")
    autocomplete_fields = ['sheet', 'data_set']
