from django.urls import reverse_lazy
from django.views import generic
from django.views.generic.edit import UpdateView, DeleteView
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from django_tables2 import RequestConfig
import pyexcel as pe

from .fieldlist import attrs
from .models import ImageData
from .models import ImageMetadata
from .models import ImageMetadataTable
from .models import Collection
from .models import CollectionTable
from .forms import CollectionForm
from .forms import ImageMetadataForm
from .forms import SignUpForm
from .forms import UploadForm
from . import tasks

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
def upload_image_metadata(request):
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
            return redirect('ingest:image_metadata_list')
    else:
        form = UploadForm()
    collections = Collection.objects.all()
    return render(request, 'ingest/image_metadata_upload.html', {'form': form, 'collections': collections})


@login_required
def image_metadata_list(request):
    """ A list of all the metadata the user has created. """
    if request.method == "POST":
        pks = request.POST.getlist("selection")
        selected_objects = ImageMetadata.objects.filter(pk__in=pks)
        selected_objects.delete()
    table = ImageMetadataTable(
        ImageMetadata.objects.filter(user=request.user), exclude=['user'])
    RequestConfig(request).configure(table)
    image_metadata = ImageMetadata.objects.all()
    return render(request, 'ingest/image_metadata_list.html', {'table': table, 'image_metadata': image_metadata})


class ImageMetadataDetail(LoginRequiredMixin, generic.DetailView):
    """ A detailed view of a single piece of metadata. """
    model = ImageMetadata
    template_name = 'ingest/image_metadata_detail.html'
    context_object_name = 'image_metadata'


@login_required
def submit_image_metadata(request):
    """ Create new image metadata. """
    if request.method == "POST":
        # We need to pass in request here, so we can use it to get the user
        form = ImageMetadataForm(request.POST, request=request)
        if form.is_valid():
            post = form.save(commit=False)
            post.save()
            return redirect('ingest:image_metadata_list')
    else:
        form = ImageMetadataForm()
    return render(request, 'ingest/image_metadata_submit.html', {'form': form})


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
def submit_collection(request):
    """ Create a collection. """
    if request.method == "POST":
        # We need to pass in request here, so we can use it to get the user
        form = CollectionForm(request.POST, request=request)
        if form.is_valid() and request.method == 'POST':
            home_dir = "/home/{}".format(settings.IMG_DATA_USER)
            data_path = "{}/bil_data/{}".format(home_dir, str(uuid.uuid4()))
            # remotely create the directory on some host using fabric and celery
            # note: you should authenticate with ssh keys, not passwords
            tasks.create_data_path.delay(data_path)
            host_and_path = "{}@{}:{}".format(
                settings.IMG_DATA_USER, settings.IMG_DATA_HOST, data_path)
            image_data = ImageData(data_path=host_and_path)
            image_data.user = request.user
            image_data.save()
            post = form.save(commit=False)
            post.data_path = image_data
            post.save()
            return redirect('ingest:collection_list')
    else:
        form = CollectionForm()
    collections = Collection.objects.all()
    return render(request, 'ingest/collection_submit.html', {'form': form, 'collections': collections})


@login_required
def collection_list(request):
    """ Show a table of all the collections. """
    table = CollectionTable(
        Collection.objects.filter(user=request.user), exclude=['user'])
    RequestConfig(request).configure(table)
    collections = Collection.objects.all()
    return render(request, 'ingest/collection_list.html', {'table': table, 'collections': collections})


@login_required
def collection_detail(request, pk):
    """ View, edit, delete, submit a particular collection. """
    collection = Collection.objects.get(id=pk)
    image_metadata_queryset = ImageMetadata.objects.filter(
        user=request.user).filter(collection=pk)
    if request.method == 'POST' and image_metadata_queryset:
        collection.locked = True
        collection.save()
        for i in image_metadata_queryset:
            i.locked = True
            i.save()
    table = ImageMetadataTable(image_metadata_queryset)
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
        'name', 'description', 'data_path'
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
        tasks.delete_data_path.delay(data_path)
        collection.delete()
        # XXX: this should give a useful message like "Collection deleted!"
        return redirect('ingest:collection_list')
    return render(request, 'ingest/collection_delete.html', {'collection': collection})
