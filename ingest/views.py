from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic

from .models import MinimalImgMetadata


class IndexView(generic.ListView):
    template_name = 'ingest/index.html'
    context_object_name = 'latest_metadata_list'

    def get_queryset(self):
        """Return the last five published metadata."""
        return MinimalImgMetadata.objects.order_by('-organization_name')[:5]


class DetailView(generic.DetailView):
    model = MinimalImgMetadata
    template_name = 'ingest/detail.html'
    context_object_name = 'metadata'
