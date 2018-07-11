from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView
from django.views.generic.edit import UpdateView, DeleteView

from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin
from django_tables2 import RequestConfig
import pyexcel as pe
from django_celery_results.models import TaskResult

import datetime
from . import tasks
from .fieldlist import attrs
from .forms import CollectionForm
from .forms import ImageMetadataForm
from .forms import SignUpForm
from .forms import UploadForm
from .models import Collection
from .models import CollectionFilter
from .models import CollectionTable
from .models import ImageData
from .models import ImageMetadata
from .models import ImageMetadataTable

import uuid


def signup(request):
    """ This is how a user signs up for a new account. """
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('/')
    else:
        form = SignUpForm()
    return render(request, 'ingest/signup.html', {'form': form})


def index(request):
    """ The main/home page. """
    return render(request, 'ingest/index.html')


# What follows is a number of views for uploading, creating, viewing, modifying
# and deleting IMAGE METADATA.


@login_required
def image_metadata_upload(request):
    """ Upload a spreadsheet containing image metadata information. """
    if request.method == 'POST' and request.FILES['myfile']:
        form = UploadForm(request.POST)
        if form.is_valid():
            associated_collection = form.cleaned_data['associated_collection']
            myfile = request.FILES['myfile']
            fs = FileSystemStorage()
            filename = fs.save(myfile.name, myfile)
            rec = pe.iget_records(file_name=filename)
            for r in rec:
                # XXX: ods format doesn't seem to stop reading after end of
                # last entry. Should add some better error handling in here to
                # deal with this.
                if not (r['project_name']):
                    break
                im = ImageMetadata(
                    collection=associated_collection,
                    project_name=r['project_name'],
                    project_description=r['project_description'],
                    background_strain=r['background_strain'],
                    image_filename_pattern=r['image_filename_pattern'],
                    taxonomy_name=r['taxonomy_name'],
                    transgenic_line_name=r['transgenic_line_name'],
                    age=r['age'],
                    age_unit=r['age_unit'],
                    sex=r['sex'],
                    organ=r['organ'],
                    organ_substructure=r['organ_substructure'],
                    assay=r['assay'],
                    slicing_direction=r['slicing_direction'],
                    user=request.user)
                im.save()
            messages.success(request, 'Metadata successfully uploaded')
            return redirect('ingest:image_metadata_list')
    else:
        form = UploadForm()
    collections = Collection.objects.filter(locked=False)
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
        image_metadata = ImageMetadata.objects.all()
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
    return render(request, 'ingest/image_metadata_create.html', {'form': form})


class ImageMetadataUpdate(LoginRequiredMixin, UpdateView):
    """ Modify an existing piece of image metadata. """
    model = ImageMetadata
    fields = attrs
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
    home_dir = "/home/{}".format(settings.IMG_DATA_USER)
    data_path = "{}/bil_data/{}/{:02d}/{}".format(home_dir, str(datetime.datetime.now().year), str(datetime.datetime.now().month), str(uuid.uuid4()))
    host_and_path = "{}@{}:{}".format(
        settings.IMG_DATA_USER, settings.IMG_DATA_HOST, data_path)
    if request.method == "POST":
        # We need to pass in request here, so we can use it to get the user
        form = CollectionForm(request.POST, request=request)
        if form.is_valid() and request.method == 'POST':
            # remotely create the directory on some host using fabric and
            # celery
            # note: you should authenticate with ssh keys, not passwords
            if not settings.FAKE_STORAGE_AREA:
                tasks.create_data_path.delay(data_path)
            image_data = ImageData(data_path=host_and_path)
            image_data.user = request.user
            image_data.save()
            post = form.save(commit=False)
            post.data_path = image_data
            post.save()
            messages.success(request, 'Collection successfully created')
            return redirect('ingest:collection_list')
    else:
        form = CollectionForm()
    collections = Collection.objects.all()
    return render(
        request,
        'ingest/collection_create.html',
        {'form': form,
         'collections': collections,
         'host_and_path': host_and_path})


class CollectionList(LoginRequiredMixin, SingleTableMixin, FilterView):

    table_class = CollectionTable
    model = Collection
    template_name = 'ingest/collection_list.html'
    filterset_class = CollectionFilter

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        table_class = CollectionTable(
            Collection.objects.filter(user=self.request.user),
            exclude=['user'])
        context['table_class'] = table_class
        context['collections'] = Collection.objects.all()
        return context

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        if kwargs["data"] is None:
            kwargs["data"] = {"locked": False}
        return kwargs


@login_required
def collection_detail(request, pk):
    """ View, edit, delete, create a particular collection. """
    collection = Collection.objects.get(id=pk)
    image_metadata_queryset = ImageMetadata.objects.filter(
        user=request.user).filter(collection=pk)
    if request.method == 'POST' and image_metadata_queryset:
        collection.locked = True
        collection.save()
        for i in image_metadata_queryset:
            i.locked = True
            i.save()
            data_path = collection.data_path.__str__()
            # This is just a test, which will be replaced with some real
            # validation and analysis in the future
        if not settings.FAKE_STORAGE_AREA:
            task = tasks.get_directory_size.delay(data_path)
            task_result = TaskResult(task_id=task.task_id)
            task_result.save()
    table = ImageMetadataTable(
        ImageMetadata.objects.filter(user=request.user),
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
    """ Delete a collection.

    Implicit in this is the deletion of the storage area (both the database
    entry and the actual remote storage area).
    """

    collection = Collection.objects.get(pk=pk)
    if request.method == 'POST':
        data_path = collection.data_path.__str__()
        if not settings.FAKE_STORAGE_AREA:
            tasks.delete_data_path.delay(data_path)
        collection.delete()
        messages.success(request, 'Collection successfully deleted')
        return redirect('ingest:collection_list')
    return render(
        request, 'ingest/collection_delete.html', {'collection': collection})
