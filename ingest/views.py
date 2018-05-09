from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views import generic
from django.views.generic.edit import UpdateView, DeleteView
from django.shortcuts import redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage

from django_tables2 import RequestConfig
import pyexcel as pe

from .models import ImageData
from .models import ImageDataTable
from .models import ImageMetadata
from .models import ImageMetadataTable
from .models import Collection
from .models import CollectionTable
from .forms import CollectionForm
from .forms import ImageMetadataForm
from .forms import SignUpForm

import uuid


def upload_image_metadata(request):
    if request.method == 'POST' and request.FILES['myfile']:
        myfile = request.FILES['myfile']
        fs = FileSystemStorage()
        filename = fs.save(myfile.name, myfile)
        rec = pe.iget_records(file_name=filename)
        for r in rec:
            print(r)
        uploaded_file_url = fs.url(filename)
        return render(request, 'ingest/upload_image_metadata.html', {
            'uploaded_file_url': uploaded_file_url
        })
    return render(request, 'ingest/upload_image_metadata.html')


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

# What follows is a number of views for creating, viewing, modifying and
# deleting IMAGE DATA.

def create_image_upload_area(request):
    """ Create new area for uploading image data. """
    return render(request, 'ingest/create_image_upload_area.html')


@login_required
def image_data_dirs_list(request):
    """ A list of all the storage areas that the user has created. """

    # This is just a placeholder. We need to asynchronously create a directory
    # on BIL's storage space with the appropriate permissions (which is
    # probably on a different machine than the django site), maybe using fabric
    # or sth like that.
    home_dir = "/crucible/brain/{}/".format(request.user)
    if request.method == 'POST':
        data_path = "{}{}".format(home_dir, str(uuid.uuid4()))
        image_data = ImageData(data_path=data_path)
        image_data.save()
    table = ImageDataTable(ImageData.objects.filter())
    RequestConfig(request).configure(table)
    return render(request, 'ingest/image_data_dirs_list.html', {'table': table})

# What follows is a number of views for creating, viewing, modifying and
# deleting IMAGE METADATA.

@login_required
def image_metadata_list(request):
    """ A list of all the metadata the user has created. """
    table = ImageMetadataTable(ImageMetadata.objects.filter(user=request.user))
    RequestConfig(request).configure(table)
    return render(request, 'ingest/image_metadata_list.html', {'table': table})


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
            return redirect('/', pk=post.pk)
    else:
        form = ImageMetadataForm()
    return render(request, 'ingest/submit_image_metadata.html', {'form': form})


class ImageMetadataUpdate(LoginRequiredMixin, UpdateView):
    """ Modify an existing piece of image metadata. """
    model = ImageMetadata
    fields = [
        'project_name', 'project_description', 'project_funder_id',
        'background_strain', 'image_filename_pattern']
    template_name = 'ingest/image_metadata_update.html'
    success_url = reverse_lazy('ingest:image_metadata_list')


class ImageMetadataDelete(LoginRequiredMixin, DeleteView):
    """ Delete an existing piece of image metadata. """
    model = ImageMetadata
    template_name = 'ingest/image_metadata_delete.html'
    success_url = reverse_lazy('ingest:image_metadata_list')


@login_required
def submit_collection(request):
    if request.method == "POST":
        # We need to pass in request here, so we can use it to get the user
        form = CollectionForm(request.POST, request=request)
        if form.is_valid():
            post = form.save(commit=False)
            post.save()
            return redirect('/', pk=post.pk)
    else:
        form = CollectionForm()
    return render(request, 'ingest/submit_collection.html', {'form': form})


@login_required
def collection_list(request):
    table = CollectionTable(Collection.objects.filter(user=request.user))
    RequestConfig(request).configure(table)
    return render(request, 'ingest/collection_list.html', {'table': table})


class CollectionDetail(LoginRequiredMixin, generic.DetailView):
    model = Collection
    template_name = 'ingest/collection_detail.html'
    context_object_name = 'collection'


class CollectionUpdate(LoginRequiredMixin, UpdateView):
    model = Collection
    fields = [
        'name','description','metadata','data_path'
        ]
    template_name='ingest/collection_update.html'
    success_url=reverse_lazy('ingest:collection_list')


class CollectionDelete(LoginRequiredMixin, DeleteView):
    model = Collection
    template_name = 'ingest/collection_delete.html'
    success_url = reverse_lazy('ingest:collection_list')
