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

from django_tables2 import RequestConfig

from .models import MinimalImgMetadata
from .models import MinimalImgTable
from .models import Collection
from .models import CollectionTable
from .forms import CollectionForm
from .forms import MinimalImagingMetadataForm
from .forms import SignUpForm

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('../index')
    else:
        form = SignUpForm()
    return render(request, 'ingest/signup.html', {'form': form})


def index(request):
    return render(request, 'ingest/index.html')


@login_required
def metadata_list(request):
    table = MinimalImgTable(MinimalImgMetadata.objects.all())
    RequestConfig(request).configure(table)
    return render(request, 'ingest/metadata_list.html', {'table': table})


class DetailView(LoginRequiredMixin, generic.DetailView):
    model = MinimalImgMetadata
    template_name = 'ingest/metadata_detail.html'
    context_object_name = 'metadata'


@login_required
def submit_metadata(request):
    if request.method == "POST":
        form = MinimalImagingMetadataForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.save()
            return redirect('../index', pk=post.pk)
    else:
        form = MinimalImagingMetadataForm()
    return render(request, 'ingest/submit_metadata.html', {'form': form})


@login_required
def submit_collection(request):
    if request.method == "POST":
        form = CollectionForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.save()
            return redirect('../index', pk=post.pk)
    else:
        form = CollectionForm()
    return render(request, 'ingest/submit_collection.html', {'form': form})


@login_required
def collection_list(request):
    table = CollectionTable(Collection.objects.all())
    RequestConfig(request).configure(table)
    return render(request, 'ingest/collection_list.html', {'table': table})


class MinimalImgMetadataUpdate(UpdateView):
    model = MinimalImgMetadata
    fields = [
        'project_name', 'project_description', 'project_funder_id',
        'background_strain', 'image_filename_pattern']
    template_name = 'ingest/metadata_update.html'
    success_url = reverse_lazy('ingest:metadata_list')


class MinimalImgMetadataDelete(DeleteView):
    model = MinimalImgMetadata
    template_name = 'ingest/metadata_delete.html'
    success_url = reverse_lazy('ingest:metadata_list')
