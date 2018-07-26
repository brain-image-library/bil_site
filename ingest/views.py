from django.conf import settings
from django.contrib import messages
from django.contrib import auth
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView
from django.views.generic.edit import UpdateView, DeleteView
from django.core.cache import cache
from django.http import Http404
from django.core.exceptions import ObjectDoesNotExist


from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin
from django_tables2 import RequestConfig
import pyexcel as pe
from django_celery_results.models import TaskResult
from celery.result import AsyncResult

from . import tasks
from .field_list import required_metadata, metadata_fields
from .filters import CollectionFilter
from .forms import CollectionForm
from .forms import ImageMetadataForm
from .forms import UploadForm
from .models import Collection
from .models import ImageMetadata
from .tables import CollectionTable
from .tables import ImageMetadataTable

import uuid
import datetime


def logout(request):
    messages.success(request, "You've successfully logged out")
    # XXX: this view should be separated from the the ingestion views and
    # placed with other authentication views to allow us to reuse the
    # authentication views with other apps (e.g. data exploration portal).
    auth.logout(request)
    # Send the user back to the login page when they log out.
    # XXX: we might want to use django's messaging system to inform them that
    # they've successfully logged out.
    return redirect('login')


def signup(request):
    """ Info about signing up for a new account. """
    return render(request, 'ingest/signup.html')


def index(request):
    """ The main/home page. """
    return render(request, 'ingest/index.html')


# What follows is a number of views for uploading, creating, viewing, modifying
# and deleting IMAGE METADATA.


@login_required
def image_metadata_upload(request):
    """ Upload a spreadsheet containing image metadata information. """
    if request.method == 'POST' and request.FILES['spreadsheet_file']:
        form = UploadForm(request.POST)
        if form.is_valid():
            associated_collection = form.cleaned_data['associated_collection']
            spreadsheet_file = request.FILES['spreadsheet_file']
            error = upload_spreadsheet(spreadsheet_file, collection, request)
            if error:
                return redirect('ingest:image_metadata_upload')
            else:
                return redirect('ingest:image_metadata_list')
    else:
        form = UploadForm()
        # Only let a user associate metadata with an unlocked collection that
        # they own
        form.fields['associated_collection'].queryset = Collection.objects.filter(
            locked=False, user=request.user)
    collections = Collection.objects.filter(locked=False, user=request.user)
    return render(
        request,
        'ingest/image_metadata_upload.html',
        {'form': form, 'collections': collections})


@login_required
def image_metadata_list(request):
    """ A list of all the metadata the user has created. """
    if request.method == "POST":
        pks = request.POST.getlist("selection")
        selected_objects = ImageMetadata.objects.filter(
            pk__in=pks, locked=False)
        selected_objects.delete()
        messages.success(request, 'Metadata successfully deleted')
        return redirect('ingest:image_metadata_list')
    else:
        table = ImageMetadataTable(
            ImageMetadata.objects.filter(user=request.user), exclude=['user'])
        RequestConfig(request).configure(table)
        image_metadata = ImageMetadata.objects.filter(user=request.user)
        return render(
            request,
            'ingest/image_metadata_list.html',
            {'table': table, 'image_metadata': image_metadata})


class ImageMetadataDetail(LoginRequiredMixin, DetailView):
    """ A detailed view of a single piece of metadata. """
    model = ImageMetadata
    template_name = 'ingest/image_metadata_detail.html'
    context_object_name = 'image_metadata'


@login_required
def image_metadata_create(request):
    """ Create new image metadata. """
    if request.method == "POST":
        # We need to pass in request here, so we can use it to get the user
        form = ImageMetadataForm(request.POST, request=request)
        if form.is_valid():
            post = form.save(commit=False)
            post.save()
            messages.success(request, 'Metadata successfully created')
            return redirect('ingest:image_metadata_list')
    else:
        form = ImageMetadataForm()
        # Only let a user associate metadata with an unlocked collection that
        # they own
        form.fields['collection'].queryset = Collection.objects.filter(
            locked=False, user=request.user)
    return render(request, 'ingest/image_metadata_create.html', {'form': form})


class ImageMetadataUpdate(LoginRequiredMixin, UpdateView):
    """ Modify an existing piece of image metadata. """
    model = ImageMetadata
    fields = metadata_fields
    template_name = 'ingest/image_metadata_update.html'
    success_url = reverse_lazy('ingest:image_metadata_list')


class ImageMetadataDelete(LoginRequiredMixin, DeleteView):
    """ Delete an existing piece of image metadata. """
    model = ImageMetadata
    template_name = 'ingest/image_metadata_delete.html'
    success_url = reverse_lazy('ingest:image_metadata_list')

# What follows is a number of views for uploading, creating, viewing, modifying
# and deleting COLLECTIONS.


@login_required
def collection_create(request):
    """ Create a collection. """
    # We cache the staging area location, so that we can show it in the GET and
    # later use it during creation (POST)
    if cache.get('host_and_path'):
        host_and_path = cache.get('host_and_path')
        data_path = cache.get('data_path')
    else:
        top_level_dir = settings.STAGING_AREA_ROOT
        data_path = "{}/bil_data/{}/{:02d}/{}".format(
            top_level_dir,
            datetime.datetime.now().year,
            datetime.datetime.now().month,
            str(uuid.uuid4()))
        host_and_path = "{}@{}:{}".format(
            request.user, settings.IMG_DATA_HOST, data_path)
        cache.set('host_and_path', host_and_path, 30)
        cache.set('data_path', data_path, 30)
    if request.method == "POST":
        # We need to pass in request here, so we can use it to get the user
        form = CollectionForm(request.POST, request=request)
        if form.is_valid():
            # remotely create the directory on some host using fabric and
            # celery
            # note: you should authenticate with ssh keys, not passwords
            if not settings.FAKE_STORAGE_AREA:
                tasks.create_data_path.delay(data_path)
            post = form.save(commit=False)
            post.data_path = host_and_path
            post.save()
            cache.delete('host_and_path')
            cache.delete('data_path')
            messages.success(request, 'Collection successfully created')
            return redirect('ingest:collection_list')
    else:
        form = CollectionForm()
    collections = Collection.objects.all()
    funder_list = [
        "1-U01-H114812-01",
        "1-U01-MH114819-01",
        "1-U01-MH114824-01",
        "1-U01-MH114825-01",
        "1-U01-MH114829-01",
        "1-U19-MH114821-01",
        "1-U19-MH114830-01",
        "1-U19-MH114831-01",
        "1-U24-MH114827-01",
        "1R24MH114788-01",
        "1R24MH114793-01",
    ]
    return render(
        request,
        'ingest/collection_create.html',
        {'form': form,
         'collections': collections,
         'funder_list': funder_list,
         'host_and_path': host_and_path})


class CollectionList(LoginRequiredMixin, SingleTableMixin, FilterView):
    """ A list of all a user's collections. """

    table_class = CollectionTable
    model = Collection
    template_name = 'ingest/collection_list.html'
    filterset_class = CollectionFilter

    def get_queryset(self, **kwargs):
        return Collection.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context['collections'] = Collection.objects.filter(user=self.request.user)
        return context

    def get_filterset_kwargs(self, filterset_class):
        """ Sets the default collection filter status. """
        kwargs = super().get_filterset_kwargs(filterset_class)
        if kwargs["data"] is None:
            kwargs["data"] = {"status": "NOT_SUBMITTED"}
        return kwargs


@login_required
def collection_data_path(request, pk):
    """ Info about the staging area for a user's collection. """

    collection = Collection.objects.get(id=pk)
    host_and_path = collection.data_path
    data_path = host_and_path.split(":")[1]

    return render(
        request,
        'ingest/collection_data_path.html',
        {'collection': collection,
         'host_and_path': host_and_path,
         'data_path': data_path})


@login_required
def collection_validation_results(request, pk):
    """ Where a user can see the results of submission & validation. """
    collection = Collection.objects.get(id=pk)

    collection.status = "NOT_SUBMITTED"
    dir_size = ""
    invalid_metadata_directories = []
    if collection.celery_task_id:
        result = AsyncResult(collection.celery_task_id)
        state = result.state
        if state == 'SUCCESS':
            analysis_results = result.get()
            if analysis_results['valid']:
                collection.status = "SUCCESS"
            else:
                collection.status = "FAILED"
                invalid_metadata_directories = analysis_results["invalid_metadata_directories"]
            dir_size = analysis_results['dir_size']
        else:
            collection.status = "PENDING"

    return render(
        request,
        'ingest/collection_validation_results.html',
        {'collection': collection,
         'dir_size': dir_size,
         'invalid_metadata_directories': invalid_metadata_directories})


@login_required
def collection_detail(request, pk):
    """ View, edit, delete, create a particular collection. """
    try:
        collection = Collection.objects.get(id=pk)
    except ObjectDoesNotExist:
        raise Http404
    # the metadata associated with this collection
    image_metadata_queryset = collection.imagemetadata_set.all()
    # this is what is triggered if the user hits "Submit collection"
    # import ipdb
    # ipdb.set_trace(context=20)
    # if request.method == 'POST' and request.FILES['spreadsheet_file']:
    if request.method == 'POST' and 'spreadsheet_file' in request.FILES:
        spreadsheet_file = request.FILES['spreadsheet_file']
        upload_spreadsheet(spreadsheet_file, collection, request)
        return redirect('ingest:collection_detail', pk=pk)
    elif request.method == 'POST' and 'submit_collection' in request.POST:
        # lock everything (collection and associated image metadata) during
        # submission and validation. if successful, keep it locked
        collection.locked = True
        metadata_dirs = []
        for im in image_metadata_queryset:
            im.locked = True
            im.save()
            metadata_dirs.append(im.directory)
        # This is just a very simple test, which will be replaced with some
        # real validation and analysis in the future
        if not settings.FAKE_STORAGE_AREA:
            data_path = collection.data_path.__str__()
            task = tasks.run_analysis.delay(data_path, metadata_dirs)
            collection.celery_task_id = task.task_id
        collection.save()
        return redirect('ingest:collection_detail', pk=pk)

    # check submission and validation status
    dir_size = ""
    if collection.celery_task_id:
        result = AsyncResult(collection.celery_task_id)
        state = result.state
        if state == 'SUCCESS':
            analysis_results = result.get()
            if analysis_results['valid']:
                collection.status = "SUCCESS"
            else:
                collection.status = "FAILED"
                # need to unlock, so user can fix problem
                collection.locked = False
                for im in image_metadata_queryset:
                    im.locked = False
                    im.save()
        else:
            collection.status = "PENDING"
    collection.save()

    table = ImageMetadataTable(
        ImageMetadata.objects.filter(user=request.user, collection=collection),
        exclude=['user', 'selection'])
    return render(
        request,
        'ingest/collection_detail.html',
        {'table': table,
         'collection': collection,
         'image_metadata_queryset': image_metadata_queryset})


class CollectionUpdate(LoginRequiredMixin, UpdateView):
    """ Edit an existing collection ."""
    model = Collection
    fields = [
        'name', 'description', 'organization_name', 'lab_name',
        'project_funder', 'project_funder_id'
    ]
    template_name = 'ingest/collection_update.html'
    success_url = reverse_lazy('ingest:collection_list')


@login_required
def collection_delete(request, pk):
    """ Delete a collection. """

    collection = Collection.objects.get(pk=pk)
    if request.method == 'POST':
        data_path = collection.data_path.__str__()
        if not settings.FAKE_STORAGE_AREA:
            # This is what deletes the actual directory associated with the
            # staging area
            tasks.delete_data_path.delay(data_path)
        collection.delete()
        messages.success(request, 'Collection successfully deleted')
        return redirect('ingest:collection_list')
    return render(
        request, 'ingest/collection_delete.html', {'collection': collection})


def upload_spreadsheet(spreadsheet_file, associated_collection, request):
    """ Helper used by image_metadata_upload and collection_detail."""
    fs = FileSystemStorage()
    filename = fs.save(spreadsheet_file.name, spreadsheet_file)
    error = False
    try:
        records = pe.iget_records(file_name=filename)
        # This is kinda inefficient, but we'll pre-scan the entire spreadsheet
        # before saving entries, so we don't get half-way uploaded
        # spreadsheets.
        for idx, record in enumerate(records):
            # XXX: right now, we're just checking for required fields that are
            # missing, but we can add whatever checks we want here.
            # XXX: blank rows in the spreadsheet that have some hidden
            # formatting can screw up this test
            missing = [k for k in record if k in required_metadata and not record[k]]
            if missing: 
                error = True
                missing_str = ", ".join(missing)
                error_msg = 'Data missing from row {} in field(s): "{}"'.format(idx+2, missing_str)
                messages.error(request, error_msg)
        if error:
            # We have to add 2 to idx because spreadsheet rows are 1-indexed
            # and first row is header
            # return redirect('ingest:image_metadata_upload')
            return error
        records = pe.iget_records(file_name=filename)
        for idx, record in enumerate(records):
            # "age" isn't required, so we need to explicitly set blank
            # entries to None or else django will get confused.
            if record['age'] == '':
                record['age'] = None
            im = ImageMetadata(
                collection=associated_collection,
                user=request.user)
            for k in record:
                setattr(im, k, record[k])    
            im.save()
        messages.success(request, 'Metadata successfully uploaded')
        # return redirect('ingest:image_metadata_list')
        return error
    except pe.exceptions.FileTypeNotSupported:
        error = True
        messages.error(request, "File type not supported")
        # return redirect('ingest:image_metadata_upload')
        return error
